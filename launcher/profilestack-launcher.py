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
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except Exception:
    pass

DEFAULT_SERVER = "https://profilestack.apanel.eu.cc"
DEFAULT_PORT = 7890
BASE_LOCAL_DIR = Path.home() / "ProfileStack"
CONFIG_DIR = BASE_LOCAL_DIR / "config"
PROFILES_LOCAL_DIR = BASE_LOCAL_DIR / "profiles"

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
    "ungoogled-chromium",
]

LOG_FILE = CONFIG_DIR / "launcher.log"


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, msg: str):
    """Sends desktop notification if available."""
    log(f"Notification: [{title}] {msg}")
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-a", "ProfileStack", title, msg],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
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


BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/128.0.0.0 Safari/537.36 ProfileStack/1.0"
)
AUTH_FILE = CONFIG_DIR / "auth.json"


# ── Profile Client Engine ────────────────────────────────────────────────────
class ProfileClient:
    def __init__(self, server_url: str = DEFAULT_SERVER, token: str = ""):
        self.server_url = server_url.rstrip("/")
        self.token = token

    def _default_headers(self) -> dict:
        return {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def _ensure_token(self):
        if self.token:
            return
        if AUTH_FILE.is_file():
            try:
                data = json.loads(AUTH_FILE.read_text())
                if data.get("server") == self.server_url and data.get("token"):
                    self.token = data["token"]
                    return
            except Exception:
                pass
        try:
            self.login("admin", "admin")
        except Exception:
            pass

    def login(self, username: str = "admin", password: str = "admin") -> str:
        url = f"{self.server_url}/api/auth/login"
        payload = json.dumps({"username": username, "password": password, "remember": True}).encode()
        h = self._default_headers()
        h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=payload, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=15) as res:
            cookie_hdr = res.headers.get("Set-Cookie", "")
            m = re.search(r"(?:ps_session|profilestack_session)=([^;]+)", cookie_hdr)
            if m:
                self.token = m.group(1)
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                AUTH_FILE.write_text(json.dumps({"server": self.server_url, "token": self.token, "username": username}))
                return self.token
        return ""

    def _req(self, endpoint: str, data=None, headers=None, method="GET"):
        self._ensure_token()
        url = f"{self.server_url}{endpoint}"
        h = self._default_headers()
        if headers:
            h.update(headers)
        if self.token:
            h["X-Session-Token"] = self.token
            h["Cookie"] = f"ps_session={self.token}; profilestack_session={self.token}"
            h["Authorization"] = f"Bearer {self.token}"

        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            return urllib.request.urlopen(req, timeout=30)
        except urllib.error.HTTPError as err:
            if err.code in (401, 403) and self.login():
                if self.token:
                    h["X-Session-Token"] = self.token
                    h["Cookie"] = f"ps_session={self.token}; profilestack_session={self.token}"
                    h["Authorization"] = f"Bearer {self.token}"
                req2 = urllib.request.Request(url, data=data, headers=h, method=method)
                return urllib.request.urlopen(req2, timeout=30)
            raise

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

            # Enforce local user read/write permissions
            for root, dirs, files in os.walk(target_dir):
                for d in dirs:
                    try: os.chmod(os.path.join(root, d), 0o755)
                    except Exception: pass
                for f in files:
                    try: os.chmod(os.path.join(root, f), 0o644)
                    except Exception: pass
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

            headers = self._default_headers()
            headers.update({
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Content-Length": str(len(body)),
            })
            if self.token:
                headers["X-Session-Token"] = self.token
                headers["Cookie"] = f"ps_session={self.token}; profilestack_session={self.token}"
                headers["Authorization"] = f"Bearer {self.token}"

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
        err = "Chromium browser not found! Please install Chromium on CachyOS: sudo pacman -S chromium"
        log(f"[!] {err}")
        notify("ProfileStack Error", err)
        return

    log(f"[*] Preparing profile '{profile_name}' via {browser_bin} (server: {server_url})...")
    notify("ProfileStack", f"Launching {profile_name} in native Chromium...")

    client = ProfileClient(server_url, token)
    try:
        p_info = client.get_profile_info(profile_name)
    except Exception as e:
        err = f"Failed to fetch profile info from {server_url}: {e}"
        log(f"[!] {err}")
        notify("ProfileStack Error", f"Profile fetch error: {e}")
        return

    local_dir = PROFILES_LOCAL_DIR / profile_name
    local_dir.mkdir(parents=True, exist_ok=True)

    log(f"[*] Synchronizing state into {local_dir}...")
    try:
        client.download_profile(profile_name, local_dir)
        log("[+] State sync complete.")
    except Exception as e:
        log(f"[!] Warning: sync-down failed ({e}), continuing with local cache if available.")

    # Remove all stale lock files and symlinks forcefully
    for p in [local_dir, local_dir / "Default"]:
        if p.is_dir():
            for item in p.iterdir():
                name_lower = item.name.lower()
                if any(k in name_lower for k in ["singleton", "lock"]):
                    try: item.unlink(missing_ok=True)
                    except Exception: pass

    # Enforce read/write permissions for local user
    for root, dirs, files in os.walk(local_dir):
        for d in dirs:
            try: os.chmod(os.path.join(root, d), 0o755)
            except Exception: pass
        for f in files:
            try: os.chmod(os.path.join(root, f), 0o644)
            except Exception: pass

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
        "--ozone-platform-hint=auto",
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
            log(f"[*] Starting local proxy wrapper for {scheme}://{host}:{port}...")
            proxy_wrapper = ProxyWrapper(scheme, host, port, parsed.username, parsed.password)
            local_proxy_port = proxy_wrapper.start()
            flags.append(f"--proxy-server=socks5://127.0.0.1:{local_proxy_port}")
        else:
            flags.append(f"--proxy-server={proxy_val}")

    start_url = p_info.get("start_url") or "https://www.google.com"
    flags.append(start_url)

    chrome_log = CONFIG_DIR / "chromium.log"
    log(f"[*] Executing browser: {' '.join(flags)}")

    proc = None
    try:
        with open(chrome_log, "a") as f_log:
            proc = subprocess.Popen(
                flags,
                stdout=f_log,
                stderr=subprocess.STDOUT,
            )

        # Check for immediate crash within 1.5s
        time.sleep(1.5)
        ret = proc.poll()
        if ret is not None:
            log(f"[!] Browser terminated immediately! Exit code: {ret}. See {chrome_log}")
            notify("ProfileStack Error", f"Browser exited immediately (code {ret}). See chromium.log")
            return

        log(f"[+] Real native browser window running (PID {proc.pid})")
        notify("ProfileStack Active", f"Real browser window opened for {profile_name}")
        proc.wait()
        log(f"[*] Browser window closed (PID {proc.pid})")
    except Exception as e:
        log(f"[!] Failed to launch browser process: {e}")
        notify("ProfileStack Error", f"Could not launch browser: {e}")
        return
    finally:
        if proxy_wrapper:
            proxy_wrapper.stop()

    log(f"[*] Syncing session state back to {server_url}...")
    notify("ProfileStack", f"Syncing {profile_name} session to server...")
    try:
        res = client.upload_profile(profile_name, local_dir)
        log(f"[+] Sync successful: {res}")
        notify("ProfileStack Synced", f"Profile {profile_name} saved to server.")
    except Exception as e:
        log(f"[!] Warning: failed to sync back to server: {e}")
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
