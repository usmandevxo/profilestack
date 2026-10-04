#!/www/wwwroot/profilestack/.venv/bin/python3
"""
ProfileStack MCP Server (Model Context Protocol 2.x)
Provides full orchestration, profile management, and browser automation control to AI agents.
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root in sys.path
PROJECT_ROOT = Path(os.environ.get("PROFILESTACK_DIR", Path(__file__).resolve().parent.parent))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from mcp.server.mcpserver import MCPServer
import app.profile_manager as pm
import app.proxy_manager as prm
import app.folder_manager as fm
import app.cdp_client as cdp
from app.config import DATA_DIR

SCREENSHOTS_DIR = DATA_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

mcp = MCPServer(
    name="profilestack",
    version="1.0.0",
    description="ProfileStack Anti-Detect Browser Cluster & Multimodal Automation Protocol",
)


# ==============================================================================
# 1. Folder Management Tools
# ==============================================================================

@mcp.tool()
def list_folders() -> str:
    """List all profile folders with stats (total profiles, colors, descriptions)."""
    folders = fm.list_folders_with_stats()
    return json.dumps(folders, indent=2)


@mcp.tool()
def create_folder(
    name: str,
    description: Optional[str] = "",
    color: Optional[str] = "#2563eb",
    folder_id: Optional[str] = None,
) -> str:
    """Create a new folder/category for organizing browser profiles."""
    try:
        res = fm.create_folder(
            name=name,
            description=description or "",
            color=color or "#2563eb",
            folder_id=folder_id,
        )
        return json.dumps({"status": "success", "folder": res})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def update_folder(
    folder_id: str,
    name: Optional[str] = None,
    description: Optional[str] = None,
    color: Optional[str] = None,
) -> str:
    """Update a folder's name, description, or color."""
    try:
        res = fm.update_folder(
            folder_id=folder_id,
            name=name,
            description=description,
            color=color,
        )
        return json.dumps({"status": "success", "folder": res})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def delete_folder(folder_id: str, move_to: Optional[str] = "default") -> str:
    """Delete a folder, reassigning contained profiles to move_to folder (defaults to 'default')."""
    try:
        res = fm.delete_folder(folder_id=folder_id, move_to=move_to or "default")
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def move_profile_to_folder(profile_name: str, target_folder_id: str) -> str:
    """Move a profile from its current folder into a new folder/category."""
    try:
        res = pm.move_profile_to_folder(name=profile_name, target_folder=target_folder_id)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ==============================================================================
# 2. Profile Management Tools
# ==============================================================================

@mcp.tool()
def list_profiles(folder_id: Optional[str] = None) -> str:
    """List browser profiles, optionally filtered by folder_id. Returns status, ports, storage, and machine spoofing."""
    profiles = pm.list_profiles(folder_id=folder_id)
    return json.dumps(profiles, indent=2)


@mcp.tool()
def get_profile_details(profile_name: str) -> str:
    """Get complete details, live metrics (CPU%, RAM), and ports of a single profile."""
    p = pm.get_profile(profile_name)
    if not p:
        return json.dumps({"error": f"Profile '{profile_name}' not found."})
    return json.dumps(p, indent=2)


@mcp.tool()
def create_profile(
    profile_name: str,
    folder: Optional[str] = "default",
    proxy: Optional[str] = "",
    start_url: Optional[str] = "",
    host_mount: Optional[str] = "",
    note: Optional[str] = "",
) -> str:
    """Create a new isolated browser profile inside a folder with persistent anti-detect machine fingerprint."""
    try:
        res = pm.create_profile(
            name=profile_name,
            folder=folder or "default",
            proxy=proxy or "",
            start_url=start_url or "",
            host_mount=host_mount or "",
            note=note or "",
        )
        return json.dumps({"status": "success", "profile": res})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def update_profile(
    profile_name: str,
    folder: Optional[str] = None,
    proxy: Optional[str] = None,
    start_url: Optional[str] = None,
    host_mount: Optional[str] = None,
    note: Optional[str] = None,
) -> str:
    """Update profile configuration settings (folder, proxy, start URL, host folder mount, note)."""
    try:
        res = pm.update_profile(
            name=profile_name,
            folder=folder,
            proxy=proxy,
            start_url=start_url,
            host_mount=host_mount,
            note=note,
        )
        return json.dumps({"status": "success", "profile": res})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def delete_profile(profile_name: str) -> str:
    """Delete a profile, destroy its Docker container, and delete on-disk browser storage."""
    try:
        res = pm.delete_profile(profile_name)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ==============================================================================
# 2. Container Lifecycle Tools
# ==============================================================================

@mcp.tool()
def start_profile(profile_name: str) -> str:
    """Start a profile's container. Returns allocated VNC web streaming port and CDP automation debug port."""
    try:
        res = pm.start_profile(profile_name)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def stop_profile(profile_name: str) -> str:
    """Stop a running profile's container to free system CPU and memory resources."""
    try:
        res = pm.stop_profile(profile_name)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def restart_profile(profile_name: str) -> str:
    """Restart a profile's container."""
    try:
        res = pm.restart_profile(profile_name)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ==============================================================================
# 3. Proxy Catalog Tools
# ==============================================================================

@mcp.tool()
def list_proxies() -> str:
    """List all saved proxies in the global proxy catalog."""
    return json.dumps(prm.list_proxies(), indent=2)


@mcp.tool()
def add_proxy(name: str, url: str, note: Optional[str] = "") -> str:
    """Add a new proxy to the catalog (e.g. socks5://user:pass@host:port)."""
    try:
        res = prm.add_proxy(name, url, note or "")
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def delete_proxy(name: str) -> str:
    """Delete a proxy from the catalog."""
    try:
        res = prm.delete_proxy(name)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def test_proxy(url: str) -> str:
    """Test a proxy URL for connectivity, latency (ms), and public egress IP address."""
    try:
        res = await prm.test_proxy(url)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ==============================================================================
# 4. System Telemetry
# ==============================================================================

@mcp.tool()
def get_system_telemetry() -> str:
    """Get host telemetry: CPU usage %, RAM used/total GB, disk used/total GB, and active profile count."""
    return json.dumps(pm.system_telemetry(), indent=2)


# ==============================================================================
# 5. Browser Automation & Inspection Tools (via CDP)
# ==============================================================================

def _get_cdp_port(profile_name: str) -> int:
    p = pm.get_profile(profile_name)
    if not p:
        raise ValueError(f"Profile '{profile_name}' not found.")
    if p["status"] != "running":
        raise ValueError(f"Profile '{profile_name}' is not running. Start it first.")
    port = p.get("cdp_port")
    if not port:
        raise ValueError(f"Profile '{profile_name}' has no active CDP port.")
    return int(port)


@mcp.tool()
async def navigate_browser(profile_name: str, url: str) -> str:
    """Navigate the profile's active browser window to a target URL."""
    try:
        port = _get_cdp_port(profile_name)
        res = await cdp.navigate_tab(port, url)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def get_active_page_details(profile_name: str) -> str:
    """Get active browser tab details: title, URL, and visible text snippet."""
    try:
        port = _get_cdp_port(profile_name)
        tabs = await cdp.get_browser_tabs(port)
        page_tabs = [t for t in tabs if t.get("type") == "page"]
        if not page_tabs:
            return json.dumps({"error": "No open page tabs found."})
        current_tab = page_tabs[0]
        text_snippet = await cdp.evaluate_script(port, "document.body.innerText.slice(0, 1000)")
        return json.dumps({
            "title": current_tab.get("title"),
            "url": current_tab.get("url"),
            "text_snippet": text_snippet,
            "ws_debug_url": current_tab.get("webSocketDebuggerUrl"),
        }, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def evaluate_javascript(profile_name: str, javascript: str) -> str:
    """Evaluate a JavaScript expression inside the profile's active browser page and return the result."""
    try:
        port = _get_cdp_port(profile_name)
        val = await cdp.evaluate_script(port, javascript)
        return json.dumps({"result": val})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def click_element(profile_name: str, selector: str) -> str:
    """Click an element on the active page matching a CSS selector."""
    try:
        port = _get_cdp_port(profile_name)
        js_code = f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return {{ found: false }};
            el.scrollIntoView({{ behavior: 'instant', block: 'center' }});
            el.click();
            return {{ found: true, tagName: el.tagName }};
        }})()
        """
        res = await cdp.evaluate_script(port, js_code)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def type_into_element(profile_name: str, selector: str, text: str) -> str:
    """Type text into an input or textarea element matching a CSS selector."""
    try:
        port = _get_cdp_port(profile_name)
        js_code = f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return {{ found: false }};
            el.focus();
            el.value = {json.dumps(text)};
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return {{ found: true, value: el.value }};
        }})()
        """
        res = await cdp.evaluate_script(port, js_code)
        return json.dumps(res)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def take_screenshot(profile_name: str) -> str:
    """Capture a screenshot of the active browser window and save to disk."""
    try:
        port = _get_cdp_port(profile_name)
        b64_data = await cdp.capture_screenshot_base64(port, format="png")
        if not b64_data:
            return json.dumps({"error": "Failed to capture screenshot data."})
        
        filename = f"{profile_name}_{int(time.time())}.png"
        filepath = SCREENSHOTS_DIR / filename
        with open(filepath, "wb") as f:
            import base64
            f.write(base64.b64decode(b64_data))
            
        return json.dumps({
            "status": "success",
            "file_path": str(filepath),
            "file_size_kb": round(len(b64_data) * 0.75 / 1024, 1),
            "url": f"/screenshots/{filename}"
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run()
