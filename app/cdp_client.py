import json
import base64
import httpx
import websockets
from typing import Dict, Any, Optional

async def get_browser_tabs(cdp_port: int) -> list:
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"http://127.0.0.1:{cdp_port}/json/list")
        if res.status_code == 200:
            return res.json()
        return []

async def get_browser_version(cdp_port: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        res = await client.get(f"http://127.0.0.1:{cdp_port}/json/version")
        if res.status_code == 200:
            return res.json()
        return {}

async def open_new_tab(cdp_port: int, url: str) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.put(f"http://127.0.0.1:{cdp_port}/json/new?{url}")
        if res.status_code == 200:
            return res.json()
        return {}

async def execute_cdp_command(ws_url: str, method: str, params: Optional[dict] = None) -> dict:
    async with websockets.connect(ws_url, max_size=20 * 1024 * 1024) as ws:
        msg_id = 1
        req = {
            "id": msg_id,
            "method": method,
            "params": params or {}
        }
        await ws.send(json.dumps(req))
        while True:
            raw = await ws.recv()
            resp = json.loads(raw)
            if resp.get("id") == msg_id:
                return resp.get("result", {})

async def navigate_tab(cdp_port: int, url: str) -> dict:
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        tab = await open_new_tab(cdp_port, url)
        return {"status": "opened_new_tab", "url": url, "tab_id": tab.get("id")}
    
    tab = page_tabs[0]
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        raise RuntimeError("No WebSocket debugger URL available for tab")
    
    result = await execute_cdp_command(ws_url, "Page.navigate", {"url": url})
    return {"status": "navigated", "frame_id": result.get("frameId"), "url": url}

async def evaluate_script(cdp_port: int, expression: str) -> Any:
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    result = await execute_cdp_command(ws_url, "Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True,
        "awaitPromise": True
    })
    return result.get("result", {}).get("value")

async def capture_screenshot_base64(cdp_port: int, format: str = "png") -> str:
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    result = await execute_cdp_command(ws_url, "Page.captureScreenshot", {"format": format})
    return result.get("data", "")

async def send_text_input(cdp_port: int, text: str, press_enter: bool = False) -> dict:
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    await execute_cdp_command(ws_url, "Input.insertText", {"text": text})
    if press_enter:
        await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13
        })
        await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13,
            "nativeVirtualKeyCode": 13
        })
    return {"status": "text_sent"}

async def send_key_event(cdp_port: int, key: str) -> dict:
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    
    key_codes = {
        "Enter": (13, "Enter"),
        "Tab": (9, "Tab"),
        "Escape": (27, "Escape"),
        "Backspace": (8, "Backspace"),
        "ArrowUp": (38, "ArrowUp"),
        "ArrowDown": (40, "ArrowDown"),
        "ArrowLeft": (37, "ArrowLeft"),
        "ArrowRight": (39, "ArrowRight"),
        "PageUp": (33, "PageUp"),
        "PageDown": (34, "PageDown"),
    }
    vk, code = key_codes.get(key, (0, key))
    
    await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
        "type": "rawKeyDown",
        "key": key,
        "code": code,
        "windowsVirtualKeyCode": vk,
        "nativeVirtualKeyCode": vk
    })
    await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
        "type": "keyUp",
        "key": key,
        "code": code,
        "windowsVirtualKeyCode": vk,
        "nativeVirtualKeyCode": vk
    })
    return {"status": "key_sent", "key": key}

async def send_mouse_action(cdp_port: int, action: str) -> dict:
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    
    if action == "scroll_up":
        await execute_cdp_command(ws_url, "Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": 400,
            "y": 400,
            "deltaX": 0,
            "deltaY": -300
        })
    elif action == "scroll_down":
        await execute_cdp_command(ws_url, "Input.dispatchMouseEvent", {
            "type": "mouseWheel",
            "x": 400,
            "y": 400,
            "deltaX": 0,
            "deltaY": 300
        })
    elif action == "right_click":
        await execute_cdp_command(ws_url, "Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": 400,
            "y": 400,
            "button": "right",
            "clickCount": 1
        })
        await execute_cdp_command(ws_url, "Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": 400,
            "y": 400,
            "button": "right"
        })
    return {"status": "action_dispatched", "action": action}


# CDP modifier bitmask: 1=Alt, 2=Ctrl, 4=Meta, 8=Shift
_MODIFIER_BITS = {"Alt": 1, "Control": 2, "Meta": 4, "Shift": 8}

# Map shortcut keys to (windowsVirtualKeyCode, code)
_KEY_VK = {
    "a": (65, "KeyA"), "b": (66, "KeyB"), "c": (67, "KeyC"), "d": (68, "KeyD"),
    "e": (69, "KeyE"), "f": (70, "KeyF"), "g": (71, "KeyG"), "h": (72, "KeyH"),
    "i": (73, "KeyI"), "j": (74, "KeyJ"), "k": (75, "KeyK"), "l": (76, "KeyL"),
    "m": (77, "KeyM"), "n": (78, "KeyN"), "o": (79, "KeyO"), "p": (80, "KeyP"),
    "q": (81, "KeyQ"), "r": (82, "KeyR"), "s": (83, "KeyS"), "t": (84, "KeyT"),
    "u": (85, "KeyU"), "v": (86, "KeyV"), "w": (87, "KeyW"), "x": (88, "KeyX"),
    "y": (89, "KeyY"), "z": (90, "KeyZ"),
    "F1": (112, "F1"), "F2": (113, "F2"), "F3": (114, "F3"), "F4": (115, "F4"),
    "F5": (116, "F5"), "F6": (117, "F6"), "F7": (118, "F7"), "F8": (119, "F8"),
    "F9": (120, "F9"), "F10": (121, "F10"), "F11": (122, "F11"), "F12": (123, "F12"),
    "Enter": (13, "Enter"), "Tab": (9, "Tab"), "Escape": (27, "Escape"),
    "Backspace": (8, "Backspace"), "Delete": (46, "Delete"),
    "ArrowUp": (38, "ArrowUp"), "ArrowDown": (40, "ArrowDown"),
    "ArrowLeft": (37, "ArrowLeft"), "ArrowRight": (39, "ArrowRight"),
    "Home": (36, "Home"), "End": (35, "End"),
    "PageUp": (33, "PageUp"), "PageDown": (34, "PageDown"),
    "+": (187, "Equal"), "-": (189, "Minus"), "=": (187, "Equal"),
    "/": (191, "Slash"), ".": (190, "Period"), ",": (188, "Comma"),
    "[": (219, "BracketLeft"), "]": (221, "BracketRight"),
}

async def send_shortcut(cdp_port: int, modifiers: list, key: str) -> dict:
    """
    Send a keyboard shortcut with modifier keys via CDP.
    modifiers: list of modifier names, e.g. ["Control"], ["Control", "Shift"]
    key: the main key, e.g. "c", "v", "a", "F5"
    """
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")

    mod_bits = 0
    for m in modifiers:
        mod_bits |= _MODIFIER_BITS.get(m, 0)

    key_lower = key.lower() if len(key) == 1 else key
    vk, code = _KEY_VK.get(key_lower, _KEY_VK.get(key, (0, key)))

    # Send modifier keydown events first
    for mod in modifiers:
        mod_vk, mod_code = {
            "Control": (17, "ControlLeft"),
            "Shift": (16, "ShiftLeft"),
            "Alt": (18, "AltLeft"),
            "Meta": (91, "MetaLeft"),
        }.get(mod, (0, mod))
        await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
            "type": "rawKeyDown",
            "key": mod,
            "code": mod_code,
            "windowsVirtualKeyCode": mod_vk,
            "nativeVirtualKeyCode": mod_vk,
            "modifiers": mod_bits,
        })

    # Send main key down + char + up
    await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
        "type": "rawKeyDown",
        "key": key,
        "code": code,
        "windowsVirtualKeyCode": vk,
        "nativeVirtualKeyCode": vk,
        "modifiers": mod_bits,
    })
    # char event for printable keys
    if len(key) == 1:
        await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
            "type": "char",
            "key": key,
            "code": code,
            "windowsVirtualKeyCode": vk,
            "nativeVirtualKeyCode": vk,
            "modifiers": mod_bits,
        })
    await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
        "type": "keyUp",
        "key": key,
        "code": code,
        "windowsVirtualKeyCode": vk,
        "nativeVirtualKeyCode": vk,
        "modifiers": mod_bits,
    })

    # Release modifier keys in reverse order
    for mod in reversed(modifiers):
        mod_vk, mod_code = {
            "Control": (17, "ControlLeft"),
            "Shift": (16, "ShiftLeft"),
            "Alt": (18, "AltLeft"),
            "Meta": (91, "MetaLeft"),
        }.get(mod, (0, mod))
        await execute_cdp_command(ws_url, "Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": mod,
            "code": mod_code,
            "windowsVirtualKeyCode": mod_vk,
            "nativeVirtualKeyCode": mod_vk,
            "modifiers": 0,
        })

    return {"status": "shortcut_sent", "modifiers": modifiers, "key": key}


async def paste_clipboard_text(cdp_port: int, text: str) -> dict:
    """
    Paste text from local clipboard into the currently focused element.
    Uses Input.insertText for instant paste without keyboard events.
    """
    tabs = await get_browser_tabs(cdp_port)
    page_tabs = [t for t in tabs if t.get("type") == "page"]
    if not page_tabs:
        raise RuntimeError("No active pages in browser")
    ws_url = page_tabs[0].get("webSocketDebuggerUrl")
    await execute_cdp_command(ws_url, "Input.insertText", {"text": text})
    return {"status": "pasted", "length": len(text)}
