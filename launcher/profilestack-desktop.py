#!/usr/bin/env python3
"""
ProfileStack Desktop Application
Standalone desktop application for ProfileStack anti-detect browser cluster.
Displays all remote profiles, manages local native Chromium browser instances
(NO virtual display / noVNC), handles real-time cloud synchronization,
and provides complete profile and proxy management.
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
import hashlib
import hmac
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import zoneinfo
except ImportError:
    zoneinfo = None

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except Exception:
    pass

APP_VERSION = "1.3.0"
DEFAULT_SERVER = "https://profilestack.apanel.eu.cc"
DEFAULT_PORT = 7898

BASE_LOCAL_DIR = Path.home() / "ProfileStack"
CONFIG_DIR = BASE_LOCAL_DIR / "config"
PROFILES_LOCAL_DIR = BASE_LOCAL_DIR / "profiles"
APP_DATA_DIR = CONFIG_DIR / "desktop-shell"
AUTH_FILE = CONFIG_DIR / "auth.json"
LOG_FILE = CONFIG_DIR / "desktop.log"

_EXCLUDE_DIRS = {
    "Cache",
    "Code Cache",
    "GPUCache",
    "ShaderCache",
    "GrShaderCache",
    "GraphiteDawnCache",
    "DawnWebGPUCache",
    "DawnGraphiteCache",
    "component_crx_cache",
    "OnDeviceHeadSuggestModel",
    "hyphen-data",
    "ZxcvbnData",
    "Crashpad",
    "Crash Reports",
    "AutofillStates",
    "CertificateRevocation",
    "Crowd Deny",
    "FileTypePolicies",
    "FirstPartySetsPreloaded",
    "MEIPreload",
    "OptimizationHints",
    "PKIMetadata",
    "PrivacySandboxAttestationsPreloaded",
    "SSLErrorAssistant",
    "SafetyTips",
    "Subresource Filter",
    "TpcdMetadata",
    "TrustTokenKeyCommitments",
    "Safe Browsing",
    "Service Worker",
}
_EXCLUDE_FILES = {"SingletonLock", "SingletonCookie", "SingletonSocket", "Lock", "LOCK"}

COMMON_BROWSER_BINS = [
    "profilestack-browser",
    "chromium",
    "ungoogled-chromium",
    "chromium-browser",
    "brave-bin",
    "brave",
    "microsoft-edge-stable",
    "microsoft-edge",
    "vivaldi",
    "google-chrome-stable",
    "google-chrome",
]


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, msg: str):
    """Sends desktop notification if notify-send is available."""
    log(f"Notification: [{title}] {msg}")
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-a", "ProfileStack Desktop", title, msg],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def setup_profilestack_browser() -> str:
    """Sets up a dedicated ~/.local/bin/profilestack-browser runner and .desktop entry."""
    bin_dir = Path.home() / ".local" / "bin"
    app_dir = Path.home() / ".local" / "share" / "applications"
    icon_dir = Path.home() / ".local" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
        app_dir.mkdir(parents=True, exist_ok=True)
        icon_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Copy / symlink icon if available
    local_icon = icon_dir / "profilestack.svg"
    if not local_icon.is_file():
        for candidate_icon in [
            BASE_LOCAL_DIR / "logo.svg",
            Path("/www/wwwroot/profilestack/app/static/img/logo.svg"),
        ]:
            if candidate_icon.is_file():
                try:
                    shutil.copy2(candidate_icon, local_icon)
                except Exception:
                    pass
                break

def find_underlying_engine() -> str:
    """Finds the real Chromium engine executable (ignoring any profilestack wrappers)."""
    for candidate in [
        BASE_LOCAL_DIR / "browser" / "chrome",
        BASE_LOCAL_DIR / "browser" / "chromium",
    ]:
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)

    for b in [
        "chromium",
        "ungoogled-chromium",
        "chromium-browser",
        "brave-bin",
        "brave",
        "microsoft-edge-stable",
        "microsoft-edge",
        "vivaldi",
        "google-chrome-stable",
        "google-chrome",
    ]:
        p = shutil.which(b)
        if p and "profilestack" not in os.path.basename(p).lower():
            return p

    return ""


def setup_profilestack_browser() -> str:
    """Registers dedicated ~/.local/bin/profilestack-browser and its .desktop launcher."""
    bin_dir = Path.home() / ".local" / "bin"
    app_dir = Path.home() / ".local" / "share" / "applications"
    bin_dir.mkdir(parents=True, exist_ok=True)
    app_dir.mkdir(parents=True, exist_ok=True)

    engine_bin = find_underlying_engine()

    runner_path = bin_dir / "profilestack-browser"
    runner_script = f"""#!/usr/bin/env bash
# ProfileStack Browser - Dedicated Anti-Detect Browser Engine Runner
set -e

# 1. If invoked with --desktop or --gui, launch ProfileStack Desktop Manager
for arg in "$@"; do
    if [ "$arg" = "--desktop" ] || [ "$arg" = "--gui" ] || [ "$arg" = "--manager" ]; then
        if command -v profilestack-desktop &>/dev/null; then
            exec profilestack-desktop
        elif [ -x "$HOME/.local/bin/profilestack-desktop" ]; then
            exec "$HOME/.local/bin/profilestack-desktop"
        fi
    fi
done

# 2. Prefer running through profilestack-desktop --browser (handles full anti-detect spoofing, extensions, and configs)
if [ -x "$HOME/.local/bin/profilestack-desktop" ]; then
    exec "$HOME/.local/bin/profilestack-desktop" --browser "$@"
elif command -v profilestack-desktop &>/dev/null; then
    exec "$(command -v profilestack-desktop)" --browser "$@"
elif [ -f "$HOME/ProfileStack/launcher/profilestack-desktop.py" ] && command -v python3 &>/dev/null; then
    exec python3 "$HOME/ProfileStack/launcher/profilestack-desktop.py" --browser "$@"
elif [ -f "/www/wwwroot/profilestack/launcher/profilestack-desktop.py" ] && command -v python3 &>/dev/null; then
    exec python3 "/www/wwwroot/profilestack/launcher/profilestack-desktop.py" --browser "$@"
fi

# 3. Fallback: locate engine and run strictly with isolated profile (NEVER personal Chrome profile)
ENGINE="{engine_bin}"
if [ -z "$ENGINE" ] || [ ! -x "$ENGINE" ]; then
    for b in chromium ungoogled-chromium chromium-browser brave-bin brave google-chrome-stable google-chrome; do
        if command -v "$b" &>/dev/null; then
            p="$(command -v "$b")"
            if [[ "$p" != *profilestack* ]]; then
                ENGINE="$p"
                break
            fi
        fi
    done
fi

if [ -z "$ENGINE" ]; then
    echo "[!] ProfileStack Browser error: No underlying Chromium engine found." >&2
    echo "    Please install Chromium: sudo pacman -S chromium (or sudo apt install chromium-browser)" >&2
    exit 1
fi

PROFILE="Default"
URLS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -p|--profile)
            PROFILE="$2"
            shift 2
            ;;
        --profile=*)
            PROFILE="${{1#*=}}"
            shift
            ;;
        -l|--list)
            echo "======================================================="
            echo "         Local ProfileStack Profiles"
            echo "======================================================="
            if [ -d "$HOME/ProfileStack/profiles" ]; then
                for d in "$HOME/ProfileStack/profiles"/*; do
                    if [ -d "$d" ]; then
                        echo "  * $(basename "$d")"
                    fi
                done
            fi
            echo "======================================================="
            exit 0
            ;;
        -h|--help)
            echo "ProfileStack Browser - Isolated Anti-Detect Browser Engine"
            echo ""
            echo "Usage:"
            echo "  profilestack-browser [options] [URL]"
            echo "  profilestack-browser -p <profile_name> [URL]"
            echo ""
            echo "Options:"
            echo "  -p, --profile <name>   Launch a specific ProfileStack profile (default: 'Default')"
            echo "  -l, --list             List all local ProfileStack profiles"
            echo "  --desktop, --gui       Launch the ProfileStack Desktop manager interface"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            URLS+=("$1")
            shift
            ;;
    esac
done

PROFILE_DIR="$HOME/ProfileStack/profiles/$PROFILE"
mkdir -p "$PROFILE_DIR"
export CHROME_DESKTOP="profilestack-browser.desktop"

ARGS=(
    --user-data-dir="$PROFILE_DIR"
    --class=ProfileStackBrowser
    --log-level=3
    --silent-debugger-extension-api
    --password-store=basic
    --no-first-run
    --no-default-browser-check
    --disable-sync
    --disable-signin-scoped-device-id
    --disable-features=AccountConsistency,DesktopIdentityConsistency,LockProfileCookieDatabase
    --disable-blink-features=AutomationControlled
    --disable-session-crashed-bubble
    --restore-last-session
    --ozone-platform-hint=auto
)

if [ ${{#URLS[@]}} -eq 0 ]; then
    exec "$ENGINE" "${{ARGS[@]}}" "https://www.google.com"
else
    exec "$ENGINE" "${{ARGS[@]}}" "${{URLS[@]}}"
fi
"""
    try:
        runner_path.write_text(runner_script, encoding="utf-8")
        runner_path.chmod(0o755)
    except Exception:
        pass

    desktop_file = app_dir / "profilestack-browser.desktop"
    desktop_entry = f"""[Desktop Entry]
Name=ProfileStack Browser
Comment=ProfileStack Anti-Detect Browser Engine
Exec={runner_path} %u
Icon=profilestack
Terminal=false
Type=Application
Categories=Network;WebBrowser;
StartupWMClass=ProfileStackBrowser
"""
    try:
        desktop_file.write_text(desktop_entry, encoding="utf-8")
        desktop_file.chmod(0o755)
    except Exception:
        pass

    return str(runner_path) if runner_path.is_file() else engine_bin


def find_browser_binary() -> str:
    """Finds the ProfileStack Browser runner or installed Chromium-based engine."""
    try:
        setup_profilestack_browser()
    except Exception:
        pass
    engine = find_underlying_engine()
    if engine:
        return engine
    bin_runner = Path.home() / ".local" / "bin" / "profilestack-browser"
    if bin_runner.is_file() and os.access(bin_runner, os.X_OK):
        return str(bin_runner)
    return ""


def generate_antidetect_extension(profile_name: str, machine: dict, local_dir: Path) -> Path:
    """Generates an unpacked Chrome extension (Manifest V3) that injects hardware & fingerprint spoofing into MAIN world."""
    ext_dir = local_dir / "_profilestack_ext"
    ext_dir.mkdir(parents=True, exist_ok=True)

    cpu_cores = machine.get("cpu_cores", 8)
    res_str = machine.get("screen_resolution", "1920x1080")
    try:
        sw, sh = [int(x) for x in res_str.lower().split("x")]
    except Exception:
        sw, sh = 1920, 1080

    tz = machine.get("timezone", "UTC")
    lang = machine.get("language", "en-US")
    gpu_mode = machine.get("gpu_mode", "swiftshader")

    # Calculate timezone offset in minutes
    tz_offset = 0
    if zoneinfo is not None:
        try:
            from datetime import datetime
            now = datetime.now(zoneinfo.ZoneInfo(tz))
            offset = now.utcoffset()
            tz_offset = int(-offset.total_seconds() / 60) if offset is not None else 0
        except Exception:
            tz_offset = 0

    if gpu_mode == "swiftshader":
        gpu_vendor = "Google Inc. (Google)"
        gpu_renderer = "ANGLE (Google, Vulkan 1.3.0 (SwiftShader Device (Subzero) (0x0000C0DE)), SwiftShader driver)"
    else:
        gpu_vendor = "Google Inc. (NVIDIA)"
        gpu_renderer = "ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0, D3D11)"

    seed_num = int(hashlib.md5(f"profilestack_{profile_name}".encode()).hexdigest()[:8], 16)

    manifest = {
        "manifest_version": 3,
        "name": f"ProfileStack Anti-Detect Engine ({profile_name})",
        "version": "1.0.0",
        "description": "Hardware and fingerprint spoofing engine for ProfileStack",
        "content_scripts": [
            {
                "matches": ["<all_urls>"],
                "js": ["inject.js"],
                "run_at": "document_start",
                "world": "MAIN",
                "all_frames": True,
                "match_about_blank": True,
            }
        ],
    }

    (ext_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    inject_js = f"""// ProfileStack Hardware & Fingerprint Anti-Detect Engine
(function() {{
  'use strict';
  const CONFIG = {{
    profile: {json.dumps(profile_name)},
    cores: {cpu_cores},
    width: {sw},
    height: {sh},
    timezone: {json.dumps(tz)},
    tz_offset: {tz_offset},
    lang: {json.dumps(lang)},
    languages: [{json.dumps(lang)}, "en-US", "en"],
    gpu_vendor: {json.dumps(gpu_vendor)},
    gpu_renderer: {json.dumps(gpu_renderer)},
    seed: {seed_num}
  }};

  // 1. Remove automation indicators
  try {{
    delete Object.getPrototypeOf(navigator).webdriver;
    Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined, configurable: true }});
  }} catch(e) {{}}

  // 2. Hardware Concurrency (CPU Cores)
  try {{
    Object.defineProperty(navigator, 'hardwareConcurrency', {{
      get: () => CONFIG.cores,
      configurable: true
    }});
  }} catch(e) {{}}

  // 3. Device Memory
  try {{
    Object.defineProperty(navigator, 'deviceMemory', {{
      get: () => 8,
      configurable: true
    }});
  }} catch(e) {{}}

  // 4. Languages
  try {{
    Object.defineProperty(navigator, 'language', {{ get: () => CONFIG.lang, configurable: true }});
    Object.defineProperty(navigator, 'languages', {{ get: () => Object.freeze(CONFIG.languages), configurable: true }});
  }} catch(e) {{}}

  // 5. Screen Resolution
  try {{
    Object.defineProperty(window.screen, 'width', {{ get: () => CONFIG.width, configurable: true }});
    Object.defineProperty(window.screen, 'height', {{ get: () => CONFIG.height, configurable: true }});
    Object.defineProperty(window.screen, 'availWidth', {{ get: () => CONFIG.width, configurable: true }});
    Object.defineProperty(window.screen, 'availHeight', {{ get: () => CONFIG.height - 40, configurable: true }});
  }} catch(e) {{}}

  // 6. Timezone Spoofing in JS
  try {{
    const origDTF = Intl.DateTimeFormat;
    const origResolved = origDTF.prototype.resolvedOptions;
    origDTF.prototype.resolvedOptions = function() {{
      const res = origResolved.apply(this, arguments);
      res.timeZone = CONFIG.timezone;
      return res;
    }};
    Date.prototype.getTimezoneOffset = function() {{
      return CONFIG.tz_offset;
    }};
  }} catch(e) {{}}

  // 7. WebGL Vendor & Renderer Spoofing
  try {{
    const UNMASKED_VENDOR_WEBGL = 0x9245;
    const UNMASKED_RENDERER_WEBGL = 0x9246;

    const patchWebGL = (proto) => {{
      if (!proto) return;
      const origGetParam = proto.getParameter;
      proto.getParameter = function(param) {{
        if (param === UNMASKED_VENDOR_WEBGL) return CONFIG.gpu_vendor;
        if (param === UNMASKED_RENDERER_WEBGL) return CONFIG.gpu_renderer;
        return origGetParam.apply(this, arguments);
      }};
    }};
    if (typeof WebGLRenderingContext !== 'undefined') patchWebGL(WebGLRenderingContext.prototype);
    if (typeof WebGL2RenderingContext !== 'undefined') patchWebGL(WebGL2RenderingContext.prototype);
  }} catch(e) {{}}

  // 8. Canvas Fingerprint Protection (Deterministic noise per profile)
  try {{
    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function() {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx && this.width > 2 && this.height > 2) {{
          const shift = (CONFIG.seed % 3) - 1;
          const img = ctx.getImageData(0, 0, 1, 1);
          img.data[0] = Math.max(0, Math.min(255, img.data[0] + shift));
          ctx.putImageData(img, 0, 0);
        }}
      }} catch(e) {{}}
      return origToDataURL.apply(this, arguments);
    }};
  }} catch(e) {{}}

  // 9. AudioContext Fingerprint Protection
  try {{
    if (typeof AudioBuffer !== 'undefined') {{
      const origGetChannelData = AudioBuffer.prototype.getChannelData;
      AudioBuffer.prototype.getChannelData = function(c) {{
        const arr = origGetChannelData.apply(this, arguments);
        if (arr && arr.length > 5) {{
          const noise = ((CONFIG.seed % 100) / 100000000);
          arr[4] += noise;
        }}
        return arr;
      }};
    }}
  }} catch(e) {{}}
}})();
"""
    (ext_dir / "inject.js").write_text(inject_js, encoding="utf-8")
    return ext_dir


def inject_profile_local_state(profile_name: str, local_dir: Path) -> str:
    """Injects deterministic DPAPI/AES encryption key into Local State for persistent cookie decryption."""
    machine_id_file = local_dir / "machine-id"
    if machine_id_file.is_file():
        try:
            stable_id = machine_id_file.read_text(encoding="utf-8").strip()
        except Exception:
            stable_id = hashlib.md5(f"profilestack_{profile_name}".encode()).hexdigest()
    else:
        stable_id = hashlib.md5(f"profilestack_{profile_name}".encode()).hexdigest()
        try:
            machine_id_file.write_text(stable_id, encoding="utf-8")
        except Exception:
            pass

    seed = f"profilestack_oscrypt_v1:{stable_id}:{profile_name}"
    aes_key = hmac.new(b"profilestack", seed.encode(), hashlib.sha256).digest()
    dpapi_prefixed = b"DPAPI" + aes_key
    encrypted_key_b64 = base64.b64encode(dpapi_prefixed).decode()

    local_state_file = local_dir / "Local State"
    ls_data = {}
    if local_state_file.is_file():
        try:
            ls_data = json.loads(local_state_file.read_text(encoding="utf-8"))
        except Exception:
            ls_data = {}
    os_crypt = ls_data.setdefault("os_crypt", {})
    if not os_crypt.get("encrypted_key"):
        os_crypt["encrypted_key"] = encrypted_key_b64

    # Pre-populate profile avatar and info_cache to eliminate Chromium's
    # "Failed to PNG encode the image" error in profile_attributes_storage.cc
    prof_sec = ls_data.setdefault("profile", {})
    info_cache = prof_sec.setdefault("info_cache", {})
    default_entry = info_cache.setdefault("Default", {})
    default_entry.setdefault("active_time", time.time())
    default_entry["avatar_icon"] = "chrome://theme/IDR_PROFILE_AVATAR_0"
    default_entry["background_color"] = -1
    default_entry["is_using_default_avatar"] = True
    default_entry["is_using_default_name"] = True
    default_entry["name"] = profile_name
    default_entry["profile_highlight_color"] = -1
    default_entry["use_gaia_picture"] = False

    try:
        local_state_file.write_text(json.dumps(ls_data, separators=(",", ":")), encoding="utf-8")
    except Exception:
        pass

    return stable_id


def inject_profile_preferences(local_dir: Path, machine: dict, profile_name: str, stable_id: str):
    """Injects anti-DICE session persistence, device ID, and cookie settings into Default/Preferences."""
    pref_file = local_dir / "Default" / "Preferences"
    pref_data = {}
    if pref_file.is_file():
        try:
            pref_data = json.loads(pref_file.read_text(encoding="utf-8"))
        except Exception:
            pref_data = {}
    prof = pref_data.setdefault("profile", {})
    prof["exit_type"] = "Normal"
    prof["exited_cleanly"] = True
    prof["avatar_index"] = 0
    prof["using_default_avatar"] = True
    prof["using_default_name"] = False
    prof["name"] = profile_name
    prof.setdefault("default_content_setting_values", {})["cookies"] = 1
    prof["cookie_controls_mode"] = 0
    prof["block_third_party_cookies"] = False

    signin = pref_data.setdefault("signin", {})
    signin["allowed"] = False
    signin["allowed_on_next_startup"] = False

    sess = pref_data.setdefault("session", {})
    sess["restore_on_startup"] = 1

    try:
        device_uuid = str(uuid.UUID(stable_id))
        gservices = pref_data.setdefault("google", {}).setdefault("services", {})
        gservices["signin_scoped_device_id"] = device_uuid
    except Exception:
        pass

    try:
        pref_file.parent.mkdir(parents=True, exist_ok=True)
        pref_file.write_text(json.dumps(pref_data, indent=2), encoding="utf-8")
    except Exception:
        pass


# ── Built-in SOCKS5/HTTP Proxy Forwarder ──────────────────────────────────────
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
                try:
                    client.close()
                except Exception:
                    pass
            if upstream:
                try:
                    upstream.close()
                except Exception:
                    pass

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
            if not chunk:
                break
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
            if not c:
                raise ConnectionError("Closed")
            buf += c
        return buf

    def _tunnel(self, c, u):
        def p(src, dst):
            try:
                while True:
                    d = src.recv(65536)
                    if not d:
                        break
                    dst.sendall(d)
            except Exception:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except Exception:
                    pass

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


# ── Profile Client Engine ────────────────────────────────────────────────────
class ProfileClient:
    def __init__(self, server_url: str = DEFAULT_SERVER, token: str = ""):
        self.server_url = server_url.rstrip("/")
        self.token = token
        self.username = ""
        self._load_stored_auth()

    def _load_stored_auth(self):
        if not self.token and AUTH_FILE.is_file():
            try:
                data = json.loads(AUTH_FILE.read_text())
                if data.get("server") == self.server_url and data.get("token"):
                    self.token = data["token"]
                    self.username = data.get("username", "")
            except Exception:
                pass

    def _default_headers(self) -> dict:
        return {
            "User-Agent": BROWSER_UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def login(self, username: str = "admin", password: str = "admin", remember: bool = True) -> str:
        url = f"{self.server_url}/api/auth/login"
        payload = json.dumps({"username": username, "password": password, "remember": remember}).encode()
        h = self._default_headers()
        h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=payload, headers=h, method="POST")
        with urllib.request.urlopen(req, timeout=15) as res:
            cookie_hdr = res.headers.get("Set-Cookie", "")
            m = re.search(r"(?:ps_session|profilestack_session)=([^;]+)", cookie_hdr)
            if m:
                self.token = m.group(1)
                self.username = username
                if remember:
                    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                    AUTH_FILE.write_text(
                        json.dumps({
                            "server": self.server_url,
                            "token": self.token,
                            "username": username,
                        }, indent=2)
                    )
                return self.token
        return ""

    def logout(self):
        self.token = ""
        self.username = ""
        if AUTH_FILE.is_file():
            try:
                AUTH_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def _req(self, endpoint: str, data=None, headers=None, method="GET", timeout=60):
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
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as err:
            if err.code in (401, 403) and self.login():
                if self.token:
                    h["X-Session-Token"] = self.token
                    h["Cookie"] = f"ps_session={self.token}; profilestack_session={self.token}"
                    h["Authorization"] = f"Bearer {self.token}"
                req2 = urllib.request.Request(url, data=data, headers=h, method=method)
                return urllib.request.urlopen(req2, timeout=timeout)
            raise

    def check_connection(self) -> dict:
        try:
            with self._req("/api/telemetry", timeout=10) as res:
                return {"connected": True, "data": json.loads(res.read().decode())}
        except Exception as e:
            return {"connected": False, "error": str(e)}

    def list_profiles(self) -> list:
        with self._req("/api/profiles", timeout=15) as res:
            return json.loads(res.read().decode())

    def list_folders(self) -> list:
        with self._req("/api/folders", timeout=15) as res:
            return json.loads(res.read().decode())

    def list_proxies(self) -> list:
        with self._req("/api/proxies", timeout=15) as res:
            return json.loads(res.read().decode())

    def get_profile_info(self, name: str) -> dict:
        with self._req(f"/api/profiles/{urllib.parse.quote(name)}", timeout=15) as res:
            return json.loads(res.read().decode())

    def create_profile(self, name: str, folder: str = "default", proxy: str = "", start_url: str = "https://www.google.com", note: str = "") -> dict:
        url = "/api/profiles"
        payload = json.dumps({
            "name": name,
            "folder": folder,
            "proxy": proxy,
            "start_url": start_url,
            "note": note,
        }).encode()
        h = {"Content-Type": "application/json"}
        with self._req(url, data=payload, headers=h, method="POST", timeout=20) as res:
            return json.loads(res.read().decode())

    def test_proxy(self, proxy_url: str) -> dict:
        url = "/api/proxies/test"
        payload = json.dumps({"url": proxy_url}).encode()
        h = {"Content-Type": "application/json"}
        with self._req(url, data=payload, headers=h, method="POST", timeout=20) as res:
            return json.loads(res.read().decode())

    def download_profile(self, name: str, target_dir: Path):
        """Downloads profile archive and extracts essential state files."""
        target_dir.mkdir(parents=True, exist_ok=True)
        export_url = f"/api/profiles/{urllib.parse.quote(name)}/export"
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_f:
            tmp_path = Path(tmp_f.name)
            with self._req(export_url, timeout=120) as res:
                shutil.copyfileobj(res, tmp_f)

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                zf.extractall(target_dir)

            subdirs = [d for d in target_dir.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and subdirs[0].name == name:
                nested = subdirs[0]
                for item in nested.iterdir():
                    shutil.move(str(item), str(target_dir / item.name))
                shutil.rmtree(nested, ignore_errors=True)

            for root, dirs, files in os.walk(target_dir):
                for d in dirs:
                    try:
                        os.chmod(os.path.join(root, d), 0o755)
                    except Exception:
                        pass
                for f in files:
                    try:
                        os.chmod(os.path.join(root, f), 0o644)
                    except Exception:
                        pass
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
            with urllib.request.urlopen(req, timeout=90) as res:
                return json.loads(res.read().decode())
        finally:
            tmp_path.unlink(missing_ok=True)


# ── Active Native Profile Manager ─────────────────────────────────────────────
class ActiveProfileManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.running: Dict[str, Dict[str, Any]] = {}

    def is_running(self, name: str) -> bool:
        with self.lock:
            info = self.running.get(name)
            if not info:
                return False
            proc = info.get("proc")
            if proc and proc.poll() is None:
                return True
            return False

    def get_running_map(self) -> Dict[str, dict]:
        with self.lock:
            cleaned = {}
            for name, info in list(self.running.items()):
                proc = info.get("proc")
                if proc and proc.poll() is None:
                    cleaned[name] = {
                        "pid": proc.pid,
                        "start_time": info.get("start_time"),
                        "uptime_sec": int(time.time() - info.get("start_time", time.time())),
                        "proxy": info.get("proxy", ""),
                    }
                else:
                    self.running.pop(name, None)
            return cleaned

    def register(self, name: str, proc: subprocess.Popen, proxy_wrapper: Optional[ProxyWrapper], proxy_str: str):
        with self.lock:
            self.running[name] = {
                "proc": proc,
                "proxy_wrapper": proxy_wrapper,
                "start_time": time.time(),
                "proxy": proxy_str,
            }

    def stop(self, name: str) -> bool:
        with self.lock:
            info = self.running.get(name)
            if not info:
                return False
            proc = info.get("proc")
            pw = info.get("proxy_wrapper")

        if proc and proc.poll() is None:
            log(f"[*] Terminating native process for profile '{name}' (PID {proc.pid})...")
            try:
                proc.terminate()
                proc.wait(timeout=4)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        if pw:
            pw.stop()

        with self.lock:
            self.running.pop(name, None)
        return True


ACTIVE_MGR = ActiveProfileManager()
CLIENT_INSTANCE = ProfileClient()


# ── Profile Launch & Sync Runner ─────────────────────────────────────────────
def launch_native_profile(profile_name: str, server_url: str = DEFAULT_SERVER, token: str = ""):
    if ACTIVE_MGR.is_running(profile_name):
        log(f"[!] Profile '{profile_name}' is already running locally.")
        notify("ProfileStack", f"Profile '{profile_name}' is already active.")
        return

    browser_bin = find_browser_binary()
    if not browser_bin:
        err = "Chromium browser not found. Install on CachyOS: sudo pacman -S chromium"
        log(f"[!] {err}")
        notify("ProfileStack Error", err)
        return

    client = ProfileClient(server_url, token)
    log(f"[*] Launching profile '{profile_name}' locally in native Chromium ({browser_bin})...")
    notify("ProfileStack", f"Preparing native window for '{profile_name}'...")

    try:
        p_info = client.get_profile_info(profile_name)
    except Exception as e:
        err = f"Failed to fetch profile info: {e}"
        log(f"[!] {err}")
        notify("ProfileStack Error", err)
        return

    local_dir = PROFILES_LOCAL_DIR / profile_name
    local_dir.mkdir(parents=True, exist_ok=True)

    # Gracefully stop remote container on the server to flush SQLite WAL journal
    try:
        client._req(f"/api/profiles/{urllib.parse.quote(profile_name)}/stop", method="POST", timeout=10)
        time.sleep(0.5)
    except Exception:
        pass

    log(f"[*] Synchronizing state from server into {local_dir}...")
    try:
        client.download_profile(profile_name, local_dir)
        log(f"[+] Download complete for '{profile_name}'.")
    except Exception as e:
        log(f"[!] Cloud sync warning ({e}), falling back to existing local profile state.")

    # Remove stale locks
    for p in [local_dir, local_dir / "Default", local_dir / "Profile 1", local_dir / "Profile 2"]:
        if p.is_dir():
            for item in p.iterdir():
                name_lower = item.name.lower()
                if any(k in name_lower for k in ["singleton", "lock"]):
                    try:
                        item.unlink(missing_ok=True)
                    except Exception:
                        pass

    # Setup profile configuration, encryption key, preferences, and anti-detect extension
    m = p_info.get("machine", {})
    stable_id = inject_profile_local_state(profile_name, local_dir)
    inject_profile_preferences(local_dir, m, profile_name, stable_id)
    ext_dir = generate_antidetect_extension(profile_name, m, local_dir)

    for root, dirs, files in os.walk(local_dir):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o755)
            except Exception:
                pass
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o644)
            except Exception:
                pass

    # Setup flags and proxy
    proxy_val = p_info.get("proxy", "")
    proxy_wrapper = None
    flags = [
        browser_bin,
        f"--user-data-dir={local_dir}",
        "--class=ProfileStackBrowser",
        f"--load-extension={ext_dir}",
        f"--disable-extensions-except={ext_dir}",
        "--log-level=3",
        "--silent-debugger-extension-api",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-signin-scoped-device-id",
        "--disable-features=AccountConsistency,DesktopIdentityConsistency,LockProfileCookieDatabase",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--force-webrtc-ip-handling-policy",
        "--disable-session-crashed-bubble",
        "--restore-last-session",
        "--ozone-platform-hint=auto",
    ]

    ua_file = local_dir / "user-agent.txt"
    if ua_file.is_file():
        ua_str = ua_file.read_text(encoding="utf-8").strip()
        if ua_str:
            flags.append(f"--user-agent={ua_str}")
    elif m.get("user_agent"):
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
            log(f"[*] Starting local authenticated proxy wrapper for {scheme}://{host}:{port}...")
            proxy_wrapper = ProxyWrapper(scheme, host, port, parsed.username, parsed.password)
            local_proxy_port = proxy_wrapper.start()
            flags.append(f"--proxy-server=socks5://127.0.0.1:{local_proxy_port}")
        else:
            flags.append(f"--proxy-server={proxy_val}")

    start_url = p_info.get("start_url") or "https://www.google.com"
    flags.append(start_url)

    # Process Environment Setup (Timezone, Language, Desktop Class)
    proc_env = os.environ.copy()
    tz = m.get("timezone", "UTC")
    if tz:
        proc_env["TZ"] = tz
    lang = m.get("language", "en-US")
    if lang:
        loc = lang.replace("-", "_") + ".UTF-8"
        proc_env["LANG"] = loc
        proc_env["LC_ALL"] = loc
    proc_env["CHROME_DESKTOP"] = "profilestack-browser.desktop"

    # CPU Core Affinity via taskset
    spoof_cores = m.get("cpu_cores", 8)
    cmd = flags
    if shutil.which("taskset") and spoof_cores:
        actual_cores = os.cpu_count() or 8
        target_cores = min(spoof_cores, actual_cores)
        if target_cores > 0:
            cmd = ["taskset", "-c", f"0-{target_cores-1}"] + flags

    chrome_log = CONFIG_DIR / "chromium.log"
    log(f"[*] Executing ProfileStack Browser: {' '.join(cmd)}")

    proc = None
    try:
        with open(chrome_log, "a", encoding="utf-8") as f_log:
            proc = subprocess.Popen(
                cmd,
                env=proc_env,
                stdout=f_log,
                stderr=subprocess.STDOUT,
            )

        time.sleep(1.2)
        ret = proc.poll()
        if ret is not None:
            err = f"Browser exited immediately (code {ret}). See {chrome_log}"
            log(f"[!] {err}")
            notify("ProfileStack Error", err)
            if proxy_wrapper:
                proxy_wrapper.stop()
            return

        ACTIVE_MGR.register(profile_name, proc, proxy_wrapper, proxy_val)
        log(f"[+] ProfileStack Browser running for '{profile_name}' (PID {proc.pid}) with isolated hardware fingerprint.")
        notify("ProfileStack Active", f"ProfileStack Browser opened for {profile_name} ({m.get('screen_resolution','1080p')}, {tz})")

        # Block in background thread until window is closed by user
        proc.wait()
        log(f"[*] ProfileStack Browser window closed for '{profile_name}' (PID {proc.pid}).")
    except Exception as e:
        log(f"[!] Error running browser process: {e}")
        notify("ProfileStack Error", f"Execution error: {e}")
        return
    finally:
        ACTIVE_MGR.stop(profile_name)
        if proxy_wrapper:
            proxy_wrapper.stop()

    log(f"[*] Uploading updated session state back to server ({server_url})...")
    notify("ProfileStack", f"Syncing {profile_name} session back to cloud...")
    try:
        res = client.upload_profile(profile_name, local_dir)
        log(f"[+] Sync successful: {res}")
        notify("ProfileStack Synced", f"Profile '{profile_name}' saved to cloud.")
    except Exception as e:
        log(f"[!] Warning: sync-back failed: {e}")
        notify("ProfileStack Warning", f"Could not sync profile to cloud: {e}")


# ── Embedded HTML UI Template ────────────────────────────────────────────────
UI_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ProfileStack Desktop</title>
  <style>
    :root {
      --bg-main: #f8fafc;
      --bg-card: #ffffff;
      --border: #e2e8f0;
      --border-hover: #cbd5e1;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --text-dim: #94a3b8;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --primary-light: #eff6ff;
      --success: #16a34a;
      --success-light: #f0fdf4;
      --danger: #dc2626;
      --danger-hover: #b91c1c;
      --danger-light: #fef2f2;
      --warning: #d97706;
      --warning-light: #fffbeb;
      --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      --font-mono: 'JetBrains Mono', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: var(--font-sans);
      background-color: var(--bg-main);
      color: var(--text-main);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }
    .app-wrap { display: flex; flex-direction: column; height: 100vh; }
    
    /* Top Header */
    header {
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-logo { width: 32px; height: 32px; display: block; }
    .brand-title { font-size: 17px; font-weight: 700; color: var(--text-main); letter-spacing: -0.01em; }
    .brand-tag {
      font-size: 11px;
      font-weight: 600;
      color: var(--primary);
      background: var(--primary-light);
      padding: 2px 8px;
      border-radius: 999px;
      border: 1px solid #bfdbfe;
    }
    .header-actions { display: flex; align-items: center; gap: 16px; }
    .telemetry-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--text-muted);
      background: #f1f5f9;
      padding: 6px 12px;
      border-radius: 6px;
      border: 1px solid var(--border);
    }
    .pulse-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--success);
      box-shadow: 0 0 0 2px rgba(22, 163, 74, 0.2);
    }
    .user-pill {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 500;
      color: var(--text-main);
    }
    .btn-logout {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text-muted);
      font-size: 12px;
      font-weight: 500;
      padding: 5px 10px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }
    .btn-logout:hover {
      background: var(--danger-light);
      border-color: #fca5a5;
      color: var(--danger);
    }

    /* Sub-bar / Controls */
    .controls-bar {
      background: var(--bg-card);
      border-bottom: 1px solid var(--border);
      padding: 10px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }
    .folder-pills { display: flex; align-items: center; gap: 8px; overflow-x: auto; }
    .folder-btn {
      background: transparent;
      border: 1px solid transparent;
      color: var(--text-muted);
      font-size: 13px;
      font-weight: 500;
      padding: 6px 12px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .folder-btn:hover { background: #f1f5f9; color: var(--text-main); }
    .folder-btn.active {
      background: var(--primary-light);
      color: var(--primary);
      border-color: #bfdbfe;
      font-weight: 600;
    }
    .folder-count {
      background: rgba(0,0,0,0.06);
      padding: 1px 6px;
      border-radius: 999px;
      font-size: 11px;
    }
    .search-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
      background: #f8fafc;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 12px;
      width: 280px;
    }
    .search-input {
      border: none;
      background: transparent;
      font-size: 13px;
      color: var(--text-main);
      outline: none;
      width: 100%;
    }
    .btn-primary {
      background: var(--primary);
      color: #fff;
      border: none;
      font-size: 13px;
      font-weight: 500;
      padding: 7px 14px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
    }
    .btn-primary:hover { background: var(--primary-hover); }
    .btn-secondary {
      background: var(--bg-card);
      border: 1px solid var(--border);
      color: var(--text-main);
      font-size: 13px;
      font-weight: 500;
      padding: 7px 12px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
    }
    .btn-secondary:hover { background: #f8fafc; border-color: var(--border-hover); }

    /* Content Area */
    main {
      flex: 1;
      padding: 24px;
      overflow-y: auto;
    }

    /* Profiles Table */
    .table-card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
      overflow: hidden;
    }
    table { width: 100%; border-collapse: collapse; text-align: left; font-size: 13px; }
    th {
      background: #f8fafc;
      padding: 12px 16px;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.05em;
    }
    td {
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
    }
    tr:last-child td { border-bottom: none; }
    tr:hover td { background-color: #fafbfc; }

    .profile-title { font-weight: 600; color: var(--text-main); font-size: 14px; }
    .profile-sub { font-size: 12px; color: var(--text-muted); font-family: var(--font-mono); }
    
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 2px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: 500;
    }
    .badge-ready { background: #f1f5f9; color: var(--text-muted); border: 1px solid var(--border); }
    .badge-running {
      background: var(--success-light);
      color: var(--success);
      border: 1px solid #bbf7d0;
      font-weight: 600;
    }
    .badge-syncing {
      background: var(--primary-light);
      color: var(--primary);
      border: 1px solid #bfdbfe;
    }
    .badge-folder { background: #f8fafc; color: #475569; border: 1px solid var(--border); }

    .action-group { display: flex; align-items: center; gap: 8px; }
    .btn-open {
      background: var(--primary);
      color: #fff;
      border: none;
      padding: 6px 14px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .btn-open:hover { background: var(--primary-hover); }
    .btn-stop {
      background: var(--danger-light);
      border: 1px solid #fca5a5;
      color: var(--danger);
      padding: 6px 14px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s;
    }
    .btn-stop:hover { background: var(--danger); color: #fff; }
    .btn-icon {
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px;
      cursor: pointer;
      color: var(--text-muted);
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }
    .btn-icon:hover { background: #f1f5f9; color: var(--text-main); }

    /* Login Overlay */
    .login-modal {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.6);
      backdrop-filter: blur(4px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
    }
    .login-card {
      background: #ffffff;
      border: 1px solid var(--border);
      border-radius: 12px;
      width: 420px;
      padding: 32px;
      box-shadow: 0 20px 25px -5px rgba(0,0,0,0.1), 0 8px 10px -6px rgba(0,0,0,0.1);
    }
    .login-header { text-align: center; margin-bottom: 24px; }
    .login-logo { width: 48px; height: 48px; margin: 0 auto 12px auto; display: block; }
    .login-title { font-size: 20px; font-weight: 700; color: var(--text-main); }
    .login-desc { font-size: 13px; color: var(--text-muted); margin-top: 4px; }
    .form-group { margin-bottom: 16px; text-align: left; }
    .form-label { display: block; font-size: 13px; font-weight: 600; color: var(--text-main); margin-bottom: 6px; }
    .form-control {
      width: 100%;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 9px 12px;
      font-size: 13px;
      outline: none;
      background: #fff;
    }
    .form-control:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.15); }
    .form-check { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-muted); }

    /* Modal standard */
    .modal-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.4);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 900;
    }
    .modal-dialog {
      background: #fff;
      border-radius: 10px;
      border: 1px solid var(--border);
      width: 500px;
      padding: 24px;
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
    }
    .modal-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .modal-head h3 { font-size: 16px; font-weight: 700; }
    .close-btn { background: none; border: none; font-size: 18px; cursor: pointer; color: var(--text-muted); }
    .modal-foot { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

    /* Toast Notification */
    .toast {
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #0f172a;
      color: #fff;
      padding: 12px 20px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 500;
      box-shadow: 0 10px 15px -3px rgba(0,0,0,0.2);
      display: none;
      z-index: 2000;
      align-items: center;
      gap: 8px;
    }
  </style>
</head>
<body>
  <div class="app-wrap">
    <!-- Top Header -->
    <header>
      <div class="brand">
        <svg class="brand-logo" viewBox="0 0 120 120">
          <g transform="translate(60, 58)">
            <path d="M 0,0 L -46,-24 L -46,26 L 0,50 Z" fill="#1e40af" />
            <path d="M 0,0 L 46,-24 L 46,26 L 0,50 Z" fill="#2563eb" />
            <path d="M 0,0 L 46,-24 L 0,-48 L -46,-24 Z" fill="#0284c7" />
            <polygon points="0,-12 11,-6 11,6 0,12 -11,6 -11,-6" fill="#38bdf8" />
          </g>
        </svg>
        <span class="brand-title">ProfileStack Desktop</span>
        <span class="brand-tag">Native Chrome Profiles</span>
      </div>

      <div class="header-actions">
        <div class="telemetry-pill">
          <div class="pulse-dot"></div>
          <span id="server-status-text">Connected: profilestack.apanel.eu.cc</span>
        </div>
        <div class="telemetry-pill">
          <span id="summary-counts">0 Profiles • 0 Active</span>
        </div>
        <div class="user-pill">
          <span id="username-display">admin</span>
          <button class="btn-logout" onclick="handleLogout()">Sign Out</button>
        </div>
      </div>
    </header>

    <!-- Sub Controls Bar -->
    <div class="controls-bar">
      <div class="folder-pills" id="folder-pills-container">
        <button class="folder-btn active" data-folder="all" onclick="filterFolder('all')">
          All Profiles <span class="folder-count" id="count-all">0</span>
        </button>
      </div>

      <div style="display:flex; align-items:center; gap:10px;">
        <div class="search-wrap">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#64748b" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input type="text" class="search-input" id="search-input" placeholder="Search profiles, proxies, tags..." oninput="handleSearch()">
        </div>
        <button class="btn-primary" onclick="openCreateModal()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
          New Profile
        </button>
        <button class="btn-secondary" onclick="loadProfiles()">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10"></polyline>
            <polyline points="1 20 1 14 7 14"></polyline>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
          </svg>
          Refresh
        </button>
      </div>
    </div>

    <!-- Main Content Table -->
    <main>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th>Profile Name</th>
              <th>Folder</th>
              <th>Proxy Configuration</th>
              <th>Fingerprint Specs</th>
              <th>Status</th>
              <th style="text-align:right;">Actions</th>
            </tr>
          </thead>
          <tbody id="profiles-tbody">
            <tr>
              <td colspan="6" style="text-align:center; padding: 40px; color: var(--text-muted);">
                Loading profiles from ProfileStack cluster...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </main>
  </div>

  <!-- Login Modal -->
  <div class="login-modal" id="login-modal" style="display:none;">
    <div class="login-card">
      <div class="login-header">
        <svg class="login-logo" viewBox="0 0 120 120">
          <g transform="translate(60, 58)">
            <path d="M 0,0 L -46,-24 L -46,26 L 0,50 Z" fill="#1e40af" />
            <path d="M 0,0 L 46,-24 L 46,26 L 0,50 Z" fill="#2563eb" />
            <path d="M 0,0 L 46,-24 L 0,-48 L -46,-24 Z" fill="#0284c7" />
            <polygon points="0,-12 11,-6 11,6 0,12 -11,6 -11,-6" fill="#38bdf8" />
          </g>
        </svg>
        <h2 class="login-title">Sign in to ProfileStack</h2>
        <p class="login-desc">Connect to your anti-detect browser cluster</p>
      </div>

      <div class="form-group">
        <label class="form-label">Cluster Server URL</label>
        <input type="text" class="form-control" id="login-server" value="https://profilestack.apanel.eu.cc">
      </div>
      <div class="form-group">
        <label class="form-label">Username</label>
        <input type="text" class="form-control" id="login-user" value="admin">
      </div>
      <div class="form-group">
        <label class="form-label">Password</label>
        <input type="password" class="form-control" id="login-pass" value="admin">
      </div>
      <div class="form-group form-check">
        <input type="checkbox" id="login-remember" checked>
        <label for="login-remember">Remember connection token locally</label>
      </div>

      <button class="btn-primary" style="width:100%; justify-content:center; padding:10px;" id="login-btn" onclick="submitLogin()">
        Connect to Cluster
      </button>
      <p id="login-error" style="color:var(--danger); font-size:12px; margin-top:10px; text-align:center; display:none;"></p>
    </div>
  </div>

  <!-- Create Profile Modal -->
  <div class="modal-backdrop" id="create-modal">
    <div class="modal-dialog">
      <div class="modal-head">
        <h3>Create Browser Profile</h3>
        <button class="close-btn" onclick="closeCreateModal()">&times;</button>
      </div>
      <div class="form-group">
        <label class="form-label">Profile Name</label>
        <input type="text" class="form-control" id="new-name" placeholder="e.g. Google-Ads-01">
      </div>
      <div class="form-group">
        <label class="form-label">Folder</label>
        <input type="text" class="form-control" id="new-folder" value="default" placeholder="default">
      </div>
      <div class="form-group">
        <label class="form-label">Proxy URL (Optional)</label>
        <input type="text" class="form-control" id="new-proxy" placeholder="socks5://user:pass@host:port or http://...">
      </div>
      <div class="form-group">
        <label class="form-label">Start URL</label>
        <input type="text" class="form-control" id="new-start-url" value="https://www.google.com">
      </div>
      <div class="form-group">
        <label class="form-label">Notes</label>
        <input type="text" class="form-control" id="new-note" placeholder="Optional profile purpose or tags">
      </div>
      <div class="modal-foot">
        <button class="btn-secondary" onclick="closeCreateModal()">Cancel</button>
        <button class="btn-primary" onclick="submitCreateProfile()">Create Profile</button>
      </div>
    </div>
  </div>

  <!-- Toast Notice -->
  <div class="toast" id="toast"></div>

  <script>
    let allProfiles = [];
    let allFolders = [];
    let runningMap = {};
    let activeFolder = 'all';

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'flex';
      setTimeout(() => { t.style.display = 'none'; }, 4000);
    }

    async function checkStatus() {
      try {
        const res = await fetch('/api/local/status');
        const data = await res.json();
        if (!data.authenticated) {
          document.getElementById('login-modal').style.display = 'flex';
        } else {
          document.getElementById('login-modal').style.display = 'none';
          document.getElementById('username-display').innerText = data.username || 'admin';
          document.getElementById('server-status-text').innerText = 'Connected: ' + (data.server_url || 'Cluster');
          loadProfiles();
        }
      } catch (e) {
        console.error('Status check error:', e);
      }
    }

    async function submitLogin() {
      const btn = document.getElementById('login-btn');
      const err = document.getElementById('login-error');
      btn.disabled = true;
      btn.innerText = 'Connecting...';
      err.style.display = 'none';

      const server_url = document.getElementById('login-server').value.trim();
      const username = document.getElementById('login-user').value.trim();
      const password = document.getElementById('login-pass').value;
      const remember = document.getElementById('login-remember').checked;

      try {
        const res = await fetch('/api/local/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ server_url, username, password, remember })
        });
        const d = await res.json();
        if (d.status === 'success') {
          document.getElementById('login-modal').style.display = 'none';
          showToast('Connected to ProfileStack cluster.');
          checkStatus();
        } else {
          err.innerText = d.error || 'Login failed';
          err.style.display = 'block';
        }
      } catch (e) {
        err.innerText = 'Connection error: ' + e.message;
        err.style.display = 'block';
      } finally {
        btn.disabled = false;
        btn.innerText = 'Connect to Cluster';
      }
    }

    async function handleLogout() {
      await fetch('/api/local/logout', { method: 'POST' });
      document.getElementById('login-modal').style.display = 'flex';
    }

    async function loadProfiles() {
      try {
        const res = await fetch('/api/local/profiles');
        const data = await res.json();
        allProfiles = data.profiles || [];
        allFolders = data.folders || [];
        runningMap = data.running || {};

        renderFolders();
        renderTable();
        updateSummary();
      } catch (e) {
        showToast('Error loading profiles: ' + e.message);
      }
    }

    function updateSummary() {
      const total = allProfiles.length;
      const active = Object.keys(runningMap).length;
      document.getElementById('summary-counts').innerText = `${total} Profiles • ${active} Active Native`;
    }

    function renderFolders() {
      const container = document.getElementById('folder-pills-container');
      const counts = { all: allProfiles.length };
      allProfiles.forEach(p => {
        const f = p.folder_id || p.folder || 'default';
        counts[f] = (counts[f] || 0) + 1;
      });

      let html = `<button class="folder-btn ${activeFolder === 'all' ? 'active' : ''}" onclick="filterFolder('all')">
        All Profiles <span class="folder-count">${counts.all}</span>
      </button>`;

      const folderKeys = Object.keys(counts).filter(k => k !== 'all');
      folderKeys.forEach(f => {
        html += `<button class="folder-btn ${activeFolder === f ? 'active' : ''}" onclick="filterFolder('${f}')">
          ${f} <span class="folder-count">${counts[f]}</span>
        </button>`;
      });

      container.innerHTML = html;
    }

    function filterFolder(folder) {
      activeFolder = folder;
      renderFolders();
      renderTable();
    }

    function handleSearch() {
      renderTable();
    }

    function renderTable() {
      const tbody = document.getElementById('profiles-tbody');
      const q = document.getElementById('search-input').value.toLowerCase().trim();

      const filtered = allProfiles.filter(p => {
        const folder = p.folder_id || p.folder || 'default';
        if (activeFolder !== 'all' && folder !== activeFolder) return false;
        if (!q) return true;
        const name = (p.name || '').toLowerCase();
        const proxy = (p.proxy || '').toLowerCase();
        const note = (p.note || '').toLowerCase();
        return name.includes(q) || proxy.includes(q) || note.includes(q);
      });

      if (filtered.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding: 40px; color: var(--text-muted);">
          No profiles found matching criteria.
        </td></tr>`;
        return;
      }

      let html = '';
      filtered.forEach(p => {
        const isRun = runningMap[p.name];
        const folder = p.folder_id || p.folder || 'default';
        const proxy = p.proxy ? p.proxy : 'Direct (No Proxy)';
        const m = p.machine || {};
        const res = m.screen_resolution || '1920x1080';
        const lang = m.language || 'en-US';

        let statusBadge = `<span class="badge badge-ready">Ready</span>`;
        let actionBtn = `<button class="btn-open" onclick="launchProfile('${p.name}')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
          Open
        </button>`;

        if (isRun) {
          statusBadge = `<span class="badge badge-running">
            <span class="pulse-dot"></span>
            Running (PID ${isRun.pid})
          </span>`;
          actionBtn = `<button class="btn-stop" onclick="stopProfile('${p.name}')">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor">
              <rect x="6" y="6" width="12" height="12"></rect>
            </svg>
            Stop
          </button>`;
        }

        const tz = m.timezone || 'UTC';
        const cores = m.cpu_cores || 8;

        html += `<tr>
          <td>
            <div class="profile-title">${p.name}</div>
            <div class="profile-sub">${p.start_url || 'https://www.google.com'}</div>
          </td>
          <td><span class="badge badge-folder">${folder}</span></td>
          <td>
            <div style="font-size:12px; font-family:var(--font-mono); color:${p.proxy ? 'var(--text-main)' : 'var(--text-muted)'}">
              ${proxy}
            </div>
          </td>
          <td>
            <div style="font-size:12px; color:var(--text-main); font-weight:500;">
              ProfileStack Engine &bull; ${res}
            </div>
            <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono); margin-top:2px;">
              TZ: ${tz} &bull; ${cores} Cores &bull; WebGL Spoofed
            </div>
          </td>
          <td>${statusBadge}</td>
          <td style="text-align:right;">
            <div class="action-group" style="justify-content:flex-end;">
              ${actionBtn}
              <button class="btn-icon" title="Manual Cloud Sync" onclick="forceSync('${p.name}')">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
              </button>
            </div>
          </td>
        </tr>`;
      });

      tbody.innerHTML = html;
    }

    async function launchProfile(name) {
      showToast(`Launching ${name} in ProfileStack Browser...`);
      try {
        const res = await fetch('/api/local/launch', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile: name })
        });
        const d = await res.json();
        if (d.status === 'launching') {
          setTimeout(loadProfiles, 1500);
        } else {
          showToast('Launch failed: ' + (d.error || 'Unknown'));
        }
      } catch (e) {
        showToast('Error: ' + e.message);
      }
    }

    async function stopProfile(name) {
      showToast(`Stopping ${name} and syncing back to cloud...`);
      try {
        const res = await fetch('/api/local/stop', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile: name })
        });
        const d = await res.json();
        setTimeout(loadProfiles, 1000);
      } catch (e) {
        showToast('Error: ' + e.message);
      }
    }

    async function forceSync(name) {
      showToast(`Syncing profile ${name}...`);
      try {
        const res = await fetch('/api/local/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ profile: name })
        });
        const d = await res.json();
        showToast(`Sync result for ${name}: ${d.status}`);
      } catch (e) {
        showToast('Sync error: ' + e.message);
      }
    }

    function openCreateModal() {
      document.getElementById('create-modal').style.display = 'flex';
    }
    function closeCreateModal() {
      document.getElementById('create-modal').style.display = 'none';
    }

    async function submitCreateProfile() {
      const name = document.getElementById('new-name').value.trim();
      const folder = document.getElementById('new-folder').value.trim() || 'default';
      const proxy = document.getElementById('new-proxy').value.trim();
      const start_url = document.getElementById('new-start-url').value.trim() || 'https://www.google.com';
      const note = document.getElementById('new-note').value.trim();

      if (!name) {
        alert('Please enter a profile name');
        return;
      }

      try {
        const res = await fetch('/api/local/create-profile', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, folder, proxy, start_url, note })
        });
        const d = await res.json();
        if (d.status === 'success') {
          closeCreateModal();
          showToast(`Profile ${name} created successfully.`);
          loadProfiles();
        } else {
          alert('Error: ' + (d.detail || d.error || 'Failed to create'));
        }
      } catch (e) {
        alert('Request error: ' + e.message);
      }
    }

    // Polling every 3 seconds for active processes
    setInterval(async () => {
      try {
        const res = await fetch('/api/local/running');
        const data = await res.json();
        runningMap = data.running || {};
        renderTable();
        updateSummary();
      } catch (e) {}
    }, 3000);

    // Initial check
    checkStatus();
  </script>
</body>
</html>
"""


# ── Local Desktop HTTP Server & Controller ────────────────────────────────────
class LocalAppServer(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(UI_HTML.encode("utf-8"))
            return

        if parsed.path == "/api/local/status":
            auth_ok = bool(CLIENT_INSTANCE.token)
            self._send_json({
                "status": "ok",
                "version": APP_VERSION,
                "authenticated": auth_ok,
                "username": CLIENT_INSTANCE.username,
                "server_url": CLIENT_INSTANCE.server_url,
                "running": ACTIVE_MGR.get_running_map(),
                "browser": find_browser_binary(),
            })
            return

        if parsed.path == "/api/local/running":
            self._send_json({"running": ACTIVE_MGR.get_running_map()})
            return

        if parsed.path == "/api/local/profiles":
            try:
                profiles = CLIENT_INSTANCE.list_profiles()
                folders = []
                try:
                    folders = CLIENT_INSTANCE.list_folders()
                except Exception:
                    pass
                self._send_json({
                    "status": "ok",
                    "profiles": profiles,
                    "folders": folders,
                    "running": ACTIVE_MGR.get_running_map(),
                })
            except Exception as e:
                self._send_json({"error": str(e)}, status=400)
            return

        self._send_json({"error": "not found"}, status=404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if parsed.path == "/api/local/login":
            server_url = payload.get("server_url", DEFAULT_SERVER)
            username = payload.get("username", "admin")
            password = payload.get("password", "admin")
            remember = payload.get("remember", True)
            CLIENT_INSTANCE.server_url = server_url.rstrip("/")
            try:
                token = CLIENT_INSTANCE.login(username, password, remember)
                if token:
                    self._send_json({"status": "success", "token": token})
                else:
                    self._send_json({"status": "error", "error": "Invalid credentials"}, status=401)
            except Exception as e:
                self._send_json({"status": "error", "error": str(e)}, status=400)
            return

        if parsed.path == "/api/local/logout":
            CLIENT_INSTANCE.logout()
            self._send_json({"status": "success"})
            return

        if parsed.path == "/api/local/launch":
            profile = payload.get("profile", "")
            if not profile:
                self._send_json({"error": "profile required"}, status=400)
                return

            threading.Thread(
                target=launch_native_profile,
                args=(profile, CLIENT_INSTANCE.server_url, CLIENT_INSTANCE.token),
                daemon=True,
            ).start()
            self._send_json({"status": "launching", "profile": profile})
            return

        if parsed.path == "/api/local/stop":
            profile = payload.get("profile", "")
            if not profile:
                self._send_json({"error": "profile required"}, status=400)
                return
            stopped = ACTIVE_MGR.stop(profile)
            self._send_json({"status": "stopped" if stopped else "not_running", "profile": profile})
            return

        if parsed.path == "/api/local/sync":
            profile = payload.get("profile", "")
            local_dir = PROFILES_LOCAL_DIR / profile
            try:
                if local_dir.is_dir():
                    res = CLIENT_INSTANCE.upload_profile(profile, local_dir)
                    self._send_json({"status": "uploaded", "result": res})
                else:
                    CLIENT_INSTANCE.download_profile(profile, local_dir)
                    self._send_json({"status": "downloaded"})
            except Exception as e:
                self._send_json({"status": "error", "error": str(e)}, status=400)
            return

        if parsed.path == "/api/local/create-profile":
            name = payload.get("name", "")
            folder = payload.get("folder", "default")
            proxy = payload.get("proxy", "")
            start_url = payload.get("start_url", "https://www.google.com")
            note = payload.get("note", "")
            try:
                res = CLIENT_INSTANCE.create_profile(name, folder, proxy, start_url, note)
                self._send_json(res)
            except Exception as e:
                self._send_json({"status": "error", "error": str(e)}, status=400)
            return

        self._send_json({"error": "not found"}, status=404)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def start_local_server(port: int = DEFAULT_PORT) -> http.server.ThreadingHTTPServer:
    # Try preferred port, otherwise pick an ephemeral open port
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), LocalAppServer)
        return server
    except OSError:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), LocalAppServer)
        return server


def open_desktop_window(url: str):
    """
    Opens the standalone Desktop Application window using Chromium's native --app mode
    or pywebview if installed.
    """
    browser_bin = find_browser_binary()
    if not browser_bin:
        log("[!] Chromium not found. Please install Chromium: sudo pacman -S chromium")
        return None

    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    flags = [
        browser_bin,
        f"--app={url}",
        f"--user-data-dir={APP_DATA_DIR}",
        "--window-size=1260,820",
        "--class=ProfileStackDesktop",
        "--name=ProfileStack Desktop",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-features=AccountConsistency,DesktopIdentityConsistency",
        "--ozone-platform-hint=auto",
    ]
    log(f"[*] Spawning ProfileStack Desktop window: {' '.join(flags)}")
    try:
        proc = subprocess.Popen(
            flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except Exception as e:
        log(f"[!] Could not open desktop window: {e}")
        return None


# ── Browser CLI Runner ───────────────────────────────────────────────────────
def browser_cli_main(cli_args: list[str]) -> int:
    """Standalone CLI runner for ProfileStack Browser."""
    profile_name = "Default"
    urls_and_flags = []
    i = 0
    show_list = False
    show_help = False

    while i < len(cli_args):
        arg = cli_args[i]
        if arg in ("-h", "--help"):
            show_help = True
            i += 1
        elif arg in ("-l", "--list"):
            show_list = True
            i += 1
        elif arg in ("-p", "--profile") and i + 1 < len(cli_args):
            profile_name = cli_args[i + 1]
            i += 2
        elif arg.startswith("--profile="):
            profile_name = arg.split("=", 1)[1]
            i += 1
        elif arg in ("--desktop", "--gui", "--manager"):
            main()
            return 0
        else:
            urls_and_flags.append(arg)
            i += 1

    if show_help:
        print("""ProfileStack Browser - Isolated Anti-Detect Browser Engine

Usage:
  profilestack-browser [options] [URL]
  profilestack-browser -p <profile_name> [URL]

Options:
  -p, --profile <name>   Launch a specific ProfileStack profile (default: 'Default')
  -l, --list             List all local ProfileStack profiles
  --desktop, --gui       Launch the ProfileStack Desktop manager interface
  -h, --help             Show this help message

Examples:
  profilestack-browser
  profilestack-browser https://google.com
  profilestack-browser -p FB_ads
  profilestack-browser --profile FossilFuel https://iphey.com
""")
        return 0

    if show_list:
        print("\n" + "=" * 55)
        print("         Local ProfileStack Profiles")
        print("=" * 55)
        PROFILES_LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        found = [d.name for d in PROFILES_LOCAL_DIR.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if not found:
            print(" No local profiles found in ~/ProfileStack/profiles.")
            print(" Run 'profilestack-desktop' to download and sync profiles.")
        else:
            for name in sorted(found):
                cfg_file = PROFILES_LOCAL_DIR / name / "config.json"
                extra = ""
                if cfg_file.is_file():
                    try:
                        cdata = json.loads(cfg_file.read_text(encoding="utf-8"))
                        p_proxy = cdata.get("proxy", "")
                        if p_proxy:
                            extra = f" (Proxy: {p_proxy})"
                    except Exception:
                        pass
                print(f"  * {name}{extra}")
        print("=" * 55 + "\n")
        return 0

    # Locate underlying Chromium engine
    engine_bin = find_underlying_engine()
    if not engine_bin:
        print("[!] ProfileStack Browser error: No underlying Chromium engine found.", file=sys.stderr)
        print("    Please install Chromium: sudo pacman -S chromium (or sudo apt install chromium-browser)", file=sys.stderr)
        return 1

    local_dir = PROFILES_LOCAL_DIR / profile_name
    local_dir.mkdir(parents=True, exist_ok=True)

    # Check for saved cloud auth and sync profile if needed
    if CLIENT_INSTANCE.token or AUTH_FILE.is_file():
        CLIENT_INSTANCE._load_stored_auth()
    if CLIENT_INSTANCE.token:
        try:
            has_cookies = (local_dir / "Default" / "Network" / "Cookies").is_file() or (local_dir / "Default" / "Cookies").is_file()
            cfg_file = local_dir / "config.json"
            if not has_cookies or not cfg_file.is_file():
                print(f"[*] Fetching profile '{profile_name}' configuration and session from cloud ({CLIENT_INSTANCE.server_url})...")
                CLIENT_INSTANCE.download_profile(profile_name, local_dir)
                print(f"[+] Synced profile '{profile_name}' state.")
        except Exception as e:
            print(f"[*] Note: Running with local profile state ({e})")

    # Clean stale locks
    for p in [local_dir, local_dir / "Default", local_dir / "Profile 1", local_dir / "Profile 2"]:
        if p.is_dir():
            for item in p.iterdir():
                name_lower = item.name.lower()
                if any(k in name_lower for k in ["singleton", "lock"]):
                    try:
                        item.unlink(missing_ok=True)
                    except Exception:
                        pass

    # Read profile config if available
    cfg_file = local_dir / "config.json"
    p_info = {}
    if cfg_file.is_file():
        try:
            p_info = json.loads(cfg_file.read_text(encoding="utf-8"))
        except Exception:
            p_info = {}

    m = p_info.get("machine", {})
    if not m:
        m = {
            "cpu_cores": 8,
            "screen_resolution": "1920x1080",
            "timezone": "UTC",
            "language": "en-US",
            "gpu_mode": "discrete",
        }

    # Setup profile configuration, encryption key, preferences, and anti-detect extension
    stable_id = inject_profile_local_state(profile_name, local_dir)
    inject_profile_preferences(local_dir, m, profile_name, stable_id)
    ext_dir = generate_antidetect_extension(profile_name, m, local_dir)

    for root, dirs, files in os.walk(local_dir):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o755)
            except Exception:
                pass
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o644)
            except Exception:
                pass

    flags = [
        engine_bin,
        f"--user-data-dir={local_dir}",
        "--class=ProfileStackBrowser",
        f"--load-extension={ext_dir}",
        f"--disable-extensions-except={ext_dir}",
        "--log-level=3",
        "--silent-debugger-extension-api",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--disable-signin-scoped-device-id",
        "--disable-features=AccountConsistency,DesktopIdentityConsistency,LockProfileCookieDatabase",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars",
        "--webrtc-ip-handling-policy=disable_non_proxied_udp",
        "--force-webrtc-ip-handling-policy",
        "--disable-session-crashed-bubble",
        "--restore-last-session",
        "--ozone-platform-hint=auto",
    ]

    ua_file = local_dir / "user-agent.txt"
    if ua_file.is_file():
        ua_str = ua_file.read_text(encoding="utf-8").strip()
        if ua_str:
            flags.append(f"--user-agent={ua_str}")
    elif m.get("user_agent"):
        flags.append(f"--user-agent={m['user_agent']}")

    if m.get("language"):
        flags.append(f"--lang={m['language']}")
    if m.get("screen_resolution"):
        flags.append(f"--window-size={m['screen_resolution'].replace('x', ',')}")

    proxy_val = p_info.get("proxy", "")
    proxy_wrapper = None
    if proxy_val:
        parsed = urllib.parse.urlparse(proxy_val)
        scheme = parsed.scheme or "socks5"
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1080
        if parsed.username and parsed.password:
            print(f"[*] Starting local authenticated proxy wrapper for {scheme}://{host}:{port}...")
            proxy_wrapper = ProxyWrapper(scheme, host, port, parsed.username, parsed.password)
            local_proxy_port = proxy_wrapper.start()
            flags.append(f"--proxy-server=socks5://127.0.0.1:{local_proxy_port}")
        else:
            flags.append(f"--proxy-server={proxy_val}")

    # Append URLs or extra flags passed by user
    has_target_url = False
    for item in urls_and_flags:
        if not item.startswith("-"):
            has_target_url = True
        flags.append(item)

    if not has_target_url:
        start_url = p_info.get("start_url") or "https://www.google.com"
        flags.append(start_url)

    proc_env = os.environ.copy()
    tz = m.get("timezone", "UTC")
    if tz:
        proc_env["TZ"] = tz
    lang = m.get("language", "en-US")
    if lang:
        loc = lang.replace("-", "_") + ".UTF-8"
        proc_env["LANG"] = loc
        proc_env["LC_ALL"] = loc
    proc_env["CHROME_DESKTOP"] = "profilestack-browser.desktop"

    spoof_cores = m.get("cpu_cores", 8)
    cmd = flags
    if shutil.which("taskset") and spoof_cores:
        actual_cores = os.cpu_count() or 8
        target_cores = min(spoof_cores, actual_cores)
        if target_cores > 0:
            cmd = ["taskset", "-c", f"0-{target_cores-1}"] + flags

    print("\n" + "=" * 65)
    print(f" ProfileStack Browser  [Profile: {profile_name}]")
    print("=" * 65)
    print(f" Data Directory: {local_dir}")
    print(f" Engine Binary:  {engine_bin}")
    print(f" Display Class:  ProfileStackBrowser")
    print(f" Fingerprint:    Active (WebGL, Canvas, Audio, {m.get('screen_resolution', '1080p')}, {tz})")
    print("=" * 65 + "\n")

    try:
        proc = subprocess.Popen(cmd, env=proc_env)
        proc.wait()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[!] Error running ProfileStack Browser: {e}", file=sys.stderr)
        return 1
    finally:
        if proxy_wrapper:
            proxy_wrapper.stop()
        if CLIENT_INSTANCE.token and (local_dir / "Default").is_dir():
            try:
                print(f"[*] Uploading updated session state for '{profile_name}' to cloud ({CLIENT_INSTANCE.server_url})...")
                res = CLIENT_INSTANCE.upload_profile(profile_name, local_dir)
                print(f"[+] Profile '{profile_name}' session saved to cloud.")
            except Exception as e:
                print(f"[*] Note: Could not sync session back to cloud: {e}")

    return 0


# ── Entry Point ──────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="ProfileStack Desktop Application")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="ProfileStack cluster server URL")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Local controller port")
    parser.add_argument("--no-window", action="store_true", help="Start background server only (no desktop window)")
    parser.add_argument("--open", dest="open_profile", help="Directly launch a profile natively by name")

    args = parser.parse_args()

    CLIENT_INSTANCE.server_url = args.server.rstrip("/")

    # If user wants to directly launch a profile via CLI
    if args.open_profile:
        launch_native_profile(args.open_profile, args.server)
        return

    # Start local HTTP server
    server = start_local_server(args.port)
    actual_port = server.server_address[1]
    app_url = f"http://127.0.0.1:{actual_port}"
    log(f"[+] ProfileStack Desktop controller active on {app_url}")

    srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
    srv_thread.start()

    window_proc = None
    if not args.no_window:
        window_proc = open_desktop_window(app_url)

    print("\n" + "=" * 65)
    print("      ProfileStack Desktop Client - Native Chrome Profiles    ")
    print("=" * 65)
    print(f"Cluster Server:   {CLIENT_INSTANCE.server_url}")
    print(f"Local Controller: {app_url}")
    print("Browser Window:   Native Desktop Application Window")
    print("=" * 65)
    print("Press Ctrl+C to quit.\n")

    try:
        if window_proc:
            # Wait for main application window to close
            window_proc.wait()
            log("[*] Desktop application window closed by user.")
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Exiting ProfileStack Desktop.")
    finally:
        # Gracefully stop any running profiles before exit
        running_names = list(ACTIVE_MGR.running.keys())
        for name in running_names:
            log(f"[*] Stopping active profile '{name}' before shutdown...")
            ACTIVE_MGR.stop(name)
        try:
            server.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--browser", "-b", "browser"):
        sys.exit(browser_cli_main(sys.argv[2:]))
    if sys.argv[0].endswith("profilestack-browser"):
        sys.exit(browser_cli_main(sys.argv[1:]))
    main()
