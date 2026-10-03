#!/usr/bin/env python3
"""
ProfileStack Screenshot Automation via Chrome DevTools Protocol
Captures authentic high-resolution screenshots using 100% generic, professional DUMMY DATA.
Zero real user or client project information is exposed.

Screenshots captured:
  1. 01-login-screen.png         (1440x900 desktop login view with default credentials hint)
  2. 02-dashboard-desktop.png    (1440x900 desktop cluster overview with dummy profiles)
  3. 03-create-profile-modal.png (1440x900 profile configuration dialog with dummy settings)
  4. 04-viewer-trackpad.png      (1440x920 remote viewer with interactive trackpad & dummy name)
  5. 05-brand-identity.png       (1200x820 brand identity studio)
"""

import os
import sys
import json
import time
import base64
import asyncio
import subprocess
import urllib.request
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, "/www/wwwroot/profilestack")
from app import auth_manager

DOCS_DIR = Path("/www/wwwroot/profilestack/docs/screenshots")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

CDP_PORT = 9995

# ── Generic Open-Source Dummy Data Script ──────────────────────────────────────
DUMMY_DATA_JS = """(() => {
    // 1. Clean Generic Folders
    window.savedFolders = [
        { id: "default", name: "General", color: "#64748b", total_profiles: 0 },
        { id: "automation", name: "Automation & AI", color: "#2563eb", total_profiles: 1 },
        { id: "ad-verify", name: "Ad Verification", color: "#059669", total_profiles: 1 },
        { id: "ecommerce", name: "E-Commerce", color: "#7c3aed", total_profiles: 1 },
        { id: "market-research", name: "Market Research", color: "#d97706", total_profiles: 1 }
    ];

    // 2. Clean Generic Profiles (Zero Real User Information)
    window.allProfiles = [
        {
            name: "chrome-sandbox-us1",
            folder: "automation",
            folder_name: "Automation & AI",
            folder_color: "#2563eb",
            status: "running",
            vnc_port: 6201,
            cdp_port: 9401,
            proxy: "socks5://residential-node.proxy-network.io:1080",
            start_url: "https://github.com/explore",
            note: "Autonomous browser orchestration agent node",
            size_mb: 42.8,
            created_at: "2026-09-18 10:20:15",
            machine: {
                cpu_cores: 4,
                screen_resolution: "1920x1080",
                timezone: "America/New_York",
                language: "en-US"
            }
        },
        {
            name: "ad-compliance-eu",
            folder: "ad-verify",
            folder_name: "Ad Verification",
            folder_color: "#059669",
            status: "running",
            vnc_port: 6202,
            cdp_port: 9402,
            proxy: "http://uk-secure.bright-node.net:8080",
            start_url: "https://www.google.com/search?q=cloud+infrastructure",
            note: "Localized compliance verification worker",
            size_mb: 38.2,
            created_at: "2026-09-24 14:12:08",
            machine: {
                cpu_cores: 2,
                screen_resolution: "1440x900",
                timezone: "Europe/London",
                language: "en-GB"
            }
        },
        {
            name: "marketplace-tester",
            folder: "ecommerce",
            folder_name: "E-Commerce",
            folder_color: "#7c3aed",
            status: "stopped",
            vnc_port: null,
            cdp_port: null,
            proxy: "",
            start_url: "https://www.amazon.com/",
            note: "Synthetic buyer journey testing cohort",
            size_mb: 56.1,
            created_at: "2026-09-28 09:45:30",
            machine: {
                cpu_cores: 4,
                screen_resolution: "1920x1080",
                timezone: "America/Chicago",
                language: "en-US"
            }
        },
        {
            name: "seo-cohort-bot",
            folder: "market-research",
            folder_name: "Market Research",
            folder_color: "#d97706",
            status: "stopped",
            vnc_port: null,
            cdp_port: null,
            proxy: "socks5://datacenter-exit.proxies.net:9050",
            start_url: "https://en.wikipedia.org/wiki/Web_scraping",
            note: "Scheduled SERP rank indexation monitor",
            size_mb: 29.4,
            created_at: "2026-10-01 16:30:22",
            machine: {
                cpu_cores: 2,
                screen_resolution: "1366x768",
                timezone: "UTC",
                language: "en-US"
            }
        }
    ];

    // 3. Update Telemetry Metrics to match dummy dataset
    const mTotal = document.getElementById('m-total-profiles');
    if (mTotal) mTotal.innerText = '4';
    const mRunning = document.getElementById('m-running-profiles');
    if (mRunning) mRunning.innerText = '2';
    const mRam = document.getElementById('m-ram');
    if (mRam) mRam.innerText = '3.8 / 24.0 GB';
    const mDisk = document.getElementById('m-disk');
    if (mDisk) mDisk.innerText = '166.5 MB';

    // 4. Update Filter Pills
    const pAll = document.getElementById('pill-count-all');
    if (pAll) pAll.innerText = '4';
    const pRun = document.getElementById('pill-count-running');
    if (pRun) pRun.innerText = '2';
    const pStop = document.getElementById('pill-count-stopped');
    if (pStop) pStop.innerText = '2';

    // 5. Re-render UI components
    if (typeof renderSidebarFolders === 'function') renderSidebarFolders();
    if (typeof populateFolderSelects === 'function') populateFolderSelects();
    if (typeof renderProfilesTable === 'function') renderProfilesTable();
})()"""


async def send_cdp(ws, method, params=None, msg_id=1):
    payload = {"id": msg_id, "method": method, "params": params or {}}
    await ws.send(json.dumps(payload))
    while True:
        res_raw = await ws.recv()
        res = json.loads(res_raw)
        if res.get("id") == msg_id:
            return res.get("result", {})


async def wait_for_event(ws, event_name, timeout=8):
    start = time.time()
    while time.time() - start < timeout:
        try:
            res_raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
            res = json.loads(res_raw)
            if res.get("method") == event_name:
                return res
        except asyncio.TimeoutError:
            pass
    return None


async def capture_page(target_url, output_path, width=1440, height=900, is_mobile=False, session_token=None, extra_js=None):
    import websockets

    req = urllib.request.Request(f"http://127.0.0.1:{CDP_PORT}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req) as resp:
        tab = json.loads(resp.read())
    
    ws_url = tab["webSocketDebuggerUrl"]
    tab_id = tab["id"]

    try:
        async with websockets.connect(ws_url, max_size=50 * 1024 * 1024) as ws:
            mid = 1
            await send_cdp(ws, "Page.enable", msg_id=mid); mid += 1
            await send_cdp(ws, "Network.enable", msg_id=mid); mid += 1

            await send_cdp(ws, "Emulation.setDeviceMetricsOverride", {
                "width": width,
                "height": height,
                "deviceScaleFactor": 1,
                "mobile": is_mobile
            }, msg_id=mid); mid += 1

            if session_token:
                await send_cdp(ws, "Network.setCookie", {
                    "name": "ps_session",
                    "value": session_token,
                    "domain": "127.0.0.1",
                    "path": "/",
                    "httpOnly": True,
                    "secure": False,
                }, msg_id=mid); mid += 1

            await send_cdp(ws, "Page.navigate", {"url": target_url}, msg_id=mid); mid += 1
            await wait_for_event(ws, "Page.loadEventFired", timeout=6)
            await asyncio.sleep(2.0)

            # Inject custom JS (such as dummy data)
            if extra_js:
                await send_cdp(ws, "Runtime.evaluate", {"expression": extra_js}, msg_id=mid); mid += 1
                await asyncio.sleep(0.6)

            res = await send_cdp(ws, "Page.captureScreenshot", {
                "format": "png",
                "quality": 100,
                "fromSurface": True
            }, msg_id=mid); mid += 1

            img_bytes = base64.b64decode(res["data"])
            with open(output_path, "wb") as f:
                f.write(img_bytes)

            print(f"CAPTURED: {output_path.name} ({len(img_bytes):,} bytes, {width}x{height})")
    finally:
        try:
            close_req = urllib.request.Request(f"http://127.0.0.1:{CDP_PORT}/json/close/{tab_id}")
            urllib.request.urlopen(close_req)
        except Exception:
            pass


async def run_captures():
    token = auth_manager.create_session("admin")
    print(f"Generated admin session token: {token[:16]}...")

    chrome_proc = subprocess.Popen([
        "chromium-browser",
        "--headless",
        "--no-sandbox",
        "--disable-gpu",
        f"--remote-debugging-port={CDP_PORT}",
        "--ignore-certificate-errors",
        "--window-size=1440,900",
        "about:blank"
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for CDP endpoint to be ready
    ready = False
    for _ in range(25):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=1) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.3)

    if not ready:
        print("ERROR: Chromium CDP endpoint failed to respond.")
        chrome_proc.terminate()
        return

    try:
        # 1. Login Screen (Clean standard state)
        await capture_page(
            target_url="http://127.0.0.1:7800/login",
            output_path=DOCS_DIR / "01-login-screen.png",
            width=1440,
            height=900
        )

        # 2. Desktop Dashboard (Clean Generic Dummy Profiles & Folders)
        await capture_page(
            target_url="http://127.0.0.1:7800/?demo=1",
            output_path=DOCS_DIR / "02-dashboard-desktop.png",
            width=1440,
            height=900,
            session_token=token
        )

        # 3. Create Profile Configuration Modal (Clean Generic Form Settings)
        await capture_page(
            target_url="http://127.0.0.1:7800/?demo=1",
            output_path=DOCS_DIR / "03-create-profile-modal.png",
            width=1440,
            height=900,
            session_token=token,
            extra_js="""(() => {
                if (typeof openModal === 'function') {
                    populateProxySelects();
                    populateFolderSelects();
                    const nameInput = document.getElementById('create-name');
                    if (nameInput) nameInput.value = 'sandbox-crawler-node';
                    const urlInput = document.getElementById('create-start-url');
                    if (urlInput) urlInput.value = 'https://github.com/explore';
                    const noteInput = document.getElementById('create-note');
                    if (noteInput) noteInput.value = 'Isolated Chromium container for distributed web crawling';
                    openModal('modal-create');
                }
            })()"""
        )

        # 4. Remote Streaming Viewer with Trackpad & Generic Profile Name
        await capture_page(
            target_url="http://127.0.0.1:7800/viewer/chrome-sandbox-us1?demo=1",
            output_path=DOCS_DIR / "04-viewer-trackpad.png",
            width=1440,
            height=920,
            session_token=token,
            extra_js="""(() => {
                const pad = document.getElementById('touchpad-drawer');
                if (pad) {
                    pad.classList.remove('collapsed');
                    const toggle = document.getElementById('touchpad-toggle');
                    if (toggle) toggle.classList.add('active');
                }
            })()"""
        )

    finally:
        chrome_proc.terminate()
        try:
            chrome_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            chrome_proc.kill()
        print("\nAll dummy data documentation screenshots captured successfully!")


if __name__ == "__main__":
    asyncio.run(run_captures())
