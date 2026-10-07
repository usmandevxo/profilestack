#!/usr/bin/env python3
"""
ProfileStack Local Launcher
Launches remote ProfileStack anti-detect browser profiles as real, native Chromium
windows on your local PC (CachyOS / Linux / macOS / Windows) with cloud sync.
"""
import argparse
import base64
import http.server
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_SERVER = "https://profilestack.apanel.eu.cc"
DEFAULT_PORT = 7890
CONFIG_DIR = Path.home() / ".config" / "profilestack"
PROFILES_LOCAL_DIR = CONFIG_DIR / "profiles"

_EXCLUDE_DIRS = {"Cache", "Code Cache", "GPUCache", "ShaderCache", "GrShaderCache", "Crashpad"}
_EXCLUDE_FILES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "Lock", "LOCK"}

COMMON_BROWSER_BINS = [
    "chromium",
    "google-chrome-stable",
    "google-chrome",
    "brave-bin",
    "brave",
    "microsoft-edge-stable",
    "microsoft-edge",
    "vivaldi",
    "cachy-browser",
]


def notify(title: str, msg: str):
    """Sends desktop notification if available."""
    if shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "-a", "ProfileStack", title, msg], check=False)
        except Exception:
            pass


def find_browser_binary() -> str:
    """Finds an installed Chromium-based browser on the host system."""
    for b in COMMON_BROWSER_BINS:
        p = shutil.which(b)
        if p:
            return p
    return ""


# ── Built-in SOCKS5/HTTP Proxy Forwarder for Authenticated Proxies ────────────
class ProxyWrapper:
    def __init__(self, scheme: str, host: str, port: int, user: str, password: str):
        self.scheme = scheme.lower()
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.server_sock = None
        self.local_port = 0
        self.running = False
        self.thread = None

    def start(self) -> int:
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind(("127.0.0.1", 0))
        self.local_port = self.server_sock.getsockname()[1]
        self.server_sock.listen(64)
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self.local_port

    def stop(self):
        self.running = False
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

    def _run(self):
        while self.running and self.server_sock:
            try:
                client, _ = self.server_sock.accept()
                threading.Thread(target=self._handle, args=(client,), daemon=True).start()
            except Exception:
                break

    def _handle(self, client: socket.socket):
        upstream = None
        try:
            upstream = socket.create_connection((self.host, self.port), timeout=10)
            if "socks" in self.scheme:
                self._auth_socks5(upstream)
            else:
                self._auth_http(client, upstream)
                return
            self._tunnel(client, upstream)
        except Exception:
            if client:
                try: client.close()
                except Exception: pass
            if upstream:
                try: upstream.close()
                except Exception: pass

    def _auth_socks5(self, upstream: socket.socket):
        upstream.sendall(b"\x05\x01\x02")
        resp = self._recv_exact(upstream, 2)
        if resp[1] != 0x02:
            raise ConnectionError("Upstream rejected auth")
        u = self.user.encode()
        p = self.password.encode()
        upstream.sendall(bytes([0x01, len(u)]) + u + bytes([len(p)]) + p)
        auth_resp = self._recv_exact(upstream, 2)
        if auth_resp[1] != 0x00:
            raise ConnectionError("Upstream auth failed")

    def _auth_http(self, client: socket.socket, upstream: socket.socket):
        req_bytes = b""
        while b"\r\n\r\n" not in req_bytes:
            chunk = client.recv(4096)
            if not chunk: break
            req_bytes += chunk
        creds = base64.b64encode(f"{self.user}:{self.password}".encode()).decode()
        hdr = f"Proxy-Authorization: Basic {creds}\r\n".encode()
        parts = req_bytes.split(b"\r\n", 1)
        modified = parts[0] + b"\r\n" + hdr + parts[1]
        upstream.sendall(modified)
        self._tunnel(client, upstream)

    def _recv_exact(self, s, n):
        buf = b""
        while len(buf) < n:
            c = s.recv(n - len(buf))
            if not c: raise ConnectionError("Closed")
            buf += c
        return buf

    def _tunnel(self, c, u):
        def p(src, dst):
            try:
                while True:
                    d = src.recv(65536)
                    if not d: break
                    dst.sendall(d)
            except Exception: pass
            finally:
                try: dst.shutdown(socket.SHUT_WR)
                except Exception: pass
        t1 = threading.Thread(target=p, args=(c, u), daemon=True)
        t2 = threading.Thread(target=p, args=(u, c), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()


# ── Profile Client Engine ────────────────────────────────────────────────────
class ProfileClient:
    def __init__(self, server_url: str = DEFAULT_SERVER, token: str = ""):
        self.server_url = server_url.rstrip("/")
        self.token = token

    def _req(self, endpoint: str, data=None, headers=None, method="GET"):
        url = f"{self.server_url}{endpoint}"
        h = headers or {}
        if self.token:
            h["X-Session-Token"] = self.token
            h["Cookie"] = f"profilestack_session={self.token}"
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        return urllib.request.urlopen(req, timeout=30)

    def get_profile_info(self, name: str) -> dict:
        with self._req(f"/api/profiles/{urllib.parse.quote(name)}") as res:
            return json.loads(res.read().decode())

    def download_profile(self, name: str, target_dir: Path):
        """Downloads profile archive and extracts essential state files."""
        target_dir.mkdir(parents=True, exist_ok=True)
        export_url = f"/api/profiles/{urllib.parse.quote(name)}/export"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_f:
            tmp_path = Path(tmp_f.name)
            with self._req(export_url) as res:
                shutil.copyfileobj(res, tmp_f)

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                zf.extractall(target_dir)

            # Move nested files if packed under single profile folder
            subdirs = [d for d in target_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and subdirs[0].name == name:
                nested = subdirs[0]
                for item in nested.iterdir():
                    shutil.move(str(item), str(target_dir / item.name))
                shutil.rmtree(nested, ignore_errors=True)
        finally:
            tmp_path.unlink(missing_ok=True)

    def upload_profile(self, name: str, source_dir: Path):
        """Packs updated cookies and session state and uploads back to server."""
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_f:
            tmp_path = Path(tmp_f.name)

        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(source_dir):
                    dirs[:] = [d for d in dirs if d not in _EXCLUDE_DIRS]
                    for f in files:
                        if f in _EXCLUDE_FILES:
                            continue
                        fpath = Path(root) / f
                        if fpath.is_file() and not fpath.is_symlink():
                            rel = fpath.relative_to(source_dir)
                            zf.write(fpath, f"{name}/{rel}")

            boundary = f"----WebKitFormBoundary{int(time.time()*1000)}"
            body = bytearray()
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="file"; filename="{name}.zip"\r\n'.encode())
            body.extend(b"Content-Type: application/zip\r\n\r\n")
            with open(tmp_path, "rb") as zf_read:
                body.extend(zf_read.read())
            body.extend(f"\r\n--{boundary}--\r\n".encode())

            headers = {
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            }
            if self.token:
                headers["X-Session-Token"] = self.token
                headers["Cookie"] = f"profilestack_session={self.token}"

            req = urllib.request.Request(
                f"{self.server_url}/api/profiles/{urllib.parse.quote(name)}/sync-back",
                data=bytes(body),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=40) as res:
                return json.loads(res.read().decode())
        finally:
            tmp_path.unlink(missing_ok=True)


# ── Launch Execution ─────────────────────────────────────────────────────────
def launch_profile(profile_name: str, server_url: str = DEFAULT_SERVER, token: str = ""):
    browser_bin = find_browser_binary()
    if not browser_bin:
        err = "No Chromium-based browser found. Install Chromium: sudo pacman -S chromium"
        print(err, file=sys.stderr)
        notify("ProfileStack Error", err)
        return

    notify("ProfileStack", f"Syncing and launching profile: {profile_name}")
    print(f"[*] Connecting to {server_url} for profile '{profile_name}'...")

    client = ProfileClient(server_url, token)
    try:
        p_info = client.get_profile_info(profile_name)
    except Exception as e:
        print(f"[!] Failed to fetch profile info: {e}")
        notify("ProfileStack Error", f"Failed to fetch profile: {e}")
        return

    local_dir = PROFILES_LOCAL_DIR / profile_name
    print(f"[*] Synchronizing state into {local_dir}...")
    try:
        client.download_profile(profile_name, local_dir)
    except Exception as e:
        print(f"[!] Warning: sync-down failed ({e}), continuing with local cache if available.")

    # Clean local lock files
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket", "LOCK"]:
        (local_dir / lock).unlink(missing_ok=True)
        (local_dir / "Default" / lock).unlink(missing_ok=True)

    # Proxy configuration
    proxy_val = p_info.get("proxy", "")
    proxy_wrapper = None
    flags = [
        browser_bin,
        f"--user-data-dir={local_dir}",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-features=LockProfileCookieDatabase",
        "--restore-last-session",
    ]

    m = p_info.get("machine", {})
    if m.get("user_agent"):
        flags.append(f"--user-agent={m['user_agent']}")
    if m.get("language"):
        flags.append(f"--lang={m['language']}")
    if m.get("screen_resolution"):
        flags.append(f"--window-size={m['screen_resolution'].replace('x', ',')}")

    if proxy_val:
        parsed = urllib.parse.urlparse(proxy_val)
        scheme = parsed.scheme or "socks5"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1080
        if parsed.username and parsed.password:
            print(f"[*] Starting local proxy wrapper for {scheme}://{host}:{port}...")
            proxy_wrapper = ProxyWrapper(scheme, host, port, parsed.username, parsed.password)
            local_proxy_port = proxy_wrapper.start()
            flags.append(f"--proxy-server=socks5://127.0.0.1:{local_proxy_port}")
        else:
            flags.append(f"--proxy-server={proxy_val}")

    start_url = p_info.get("start_url") or "https://www.google.com"
    flags.append(start_url)

    print(f"[*] Launching REAL native browser window: {browser_bin}")
    print(f"[*] Flags: {' '.join(flags)}")
    notify("ProfileStack Active", f"Real browser window opened for {profile_name}")

    try:
        proc = subprocess.Popen(flags)
        proc.wait()
    finally:
        if proxy_wrapper:
            proxy_wrapper.stop()

    print("[*] Browser closed. Syncing session and cookies back to cloud...")
    notify("ProfileStack", f"Syncing {profile_name} session to server...")
    try:
        res = client.upload_profile(profile_name, local_dir)
        print(f"[+] Sync successful: {res}")
        notify("ProfileStack Synced", f"Profile {profile_name} saved to server.")
    except Exception as e:
        print(f"[!] Warning: failed to sync back to server: {e}")
        notify("ProfileStack Sync Warning", f"Could not sync to cloud: {e}")


# ── Local Companion Daemon ───────────────────────────────────────────────────
class DaemonHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)

        if parsed.path == "/status":
            self._send_json({"status": "ready", "version": "1.0.0", "browser": find_browser_binary()})
            return

        if parsed.path == "/launch":
            profile = qs.get("profile", [""])[0]
            server = qs.get("server", [DEFAULT_SERVER])[0]
            token = qs.get("token", [""])[0]
            if not profile:
                self._send_json({"error": "profile parameter required"}, status=400)
                return

            threading.Thread(target=launch_profile, args=(profile, server, token), daemon=True).start()
            self._send_json({"status": "launching", "profile": profile})
            return

        self._send_json({"error": "not found"}, status=404)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def run_daemon(port: int = DEFAULT_PORT):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), DaemonHandler)
    print(f"[*] ProfileStack Local Daemon listening on http://127.0.0.1:{port}")
    notify("ProfileStack Daemon", f"Listening on port {port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping daemon.")


# ── Entrypoint ───────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) > 1 and sys.argv[1].startswith("profilestack://"):
        raw_url = sys.argv[1]
        parsed = urllib.parse.urlparse(raw_url)
        # handle profilestack://open?profile=x or profilestack://launch?profile=x
        qs = urllib.parse.parse_qs(parsed.query)
        profile = qs.get("profile", [""])[0] or parsed.netloc or parsed.path.strip("/")
        server = qs.get("server", [DEFAULT_SERVER])[0]
        token = qs.get("token", [""])[0]
        if profile:
            launch_profile(profile, server, token)
        return

    parser = argparse.ArgumentParser(description="ProfileStack Native Browser Launcher")
    subparsers = parser.add_subparsers(dest="cmd")

    launch_cmd = subparsers.add_parser("launch", help="Launch a remote profile locally")
    launch_cmd.add_argument("profile", help="Profile name")
    launch_cmd.add_argument("--server", default=DEFAULT_SERVER, help="Server URL")
    launch_cmd.add_argument("--token", default="", help="Session auth token")

    daemon_cmd = subparsers.add_parser("daemon", help="Run local companion daemon")
    daemon_cmd.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port to listen on")

    args = parser.parse_args()

    if args.cmd == "launch":
        launch_profile(args.profile, args.server, args.token)
    elif args.cmd == "daemon":
        run_daemon(args.port)
    else:
        # Default with 1 arg treated as profile name
        if len(sys.argv) == 2 and not sys.argv[1].startswith("-"):
            launch_profile(sys.argv[1])
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
