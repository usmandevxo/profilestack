import json
import os
import time
from pathlib import Path
import httpx
from app.config import PROXIES_FILE
from app.validator import validate_proxy_url


def _load_proxies() -> dict:
    if PROXIES_FILE.exists():
        try:
            with open(PROXIES_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_proxies(data: dict) -> None:
    tmp = str(PROXIES_FILE) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, PROXIES_FILE)


def list_proxies() -> list:
    data = _load_proxies()
    return [{"name": k, "url": v.get("url", ""), "note": v.get("note", "")} for k, v in data.items()]


def get_proxy(name: str):
    data = _load_proxies()
    return data.get(name)


def add_proxy(name: str, url: str, note: str = "") -> dict:
    name = name.strip()
    if not name or len(name) > 64:
        raise ValueError("Proxy name must be between 1 and 64 characters.")
    url = validate_proxy_url(url)
    if not url:
        raise ValueError("Proxy URL cannot be empty.")
    data = _load_proxies()
    data[name] = {"url": url, "note": note.strip()}
    _save_proxies(data)
    return {"name": name, "url": url, "note": note}


def delete_proxy(name: str) -> dict:
    data = _load_proxies()
    if name not in data:
        raise ValueError(f"Proxy '{name}' not found.")
    del data[name]
    _save_proxies(data)
    return {"status": "deleted", "name": name}


def resolve_proxy_url(proxy_field: str) -> str:
    """If proxy_field is a saved proxy name, resolves it. Otherwise returns as custom URL."""
    val = (proxy_field or "").strip()
    if not val:
        return ""
    data = _load_proxies()
    if val in data:
        return data[val].get("url", "")
    return val


async def test_proxy(proxy_url: str) -> dict:
    resolved = resolve_proxy_url(proxy_url)
    if not resolved:
        raise ValueError("Empty proxy URL")
    
    start_time = time.time()
    try:
        # Test connecting through proxy to a lightweight IP reflection service
        async with httpx.AsyncClient(proxy=resolved, timeout=10.0) as client:
            resp = await client.get("https://api.ipify.org?format=json")
            latency_ms = round((time.time() - start_time) * 1000, 1)
            if resp.status_code == 200:
                ip_data = resp.json()
                return {
                    "status": "success",
                    "ip": ip_data.get("ip", "unknown"),
                    "latency_ms": latency_ms
                }
            return {
                "status": "error",
                "message": f"HTTP {resp.status_code}",
                "latency_ms": latency_ms
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "latency_ms": round((time.time() - start_time) * 1000, 1)
        }

# [ProfileStack v1.17.90] revision checkpoint
