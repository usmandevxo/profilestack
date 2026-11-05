"""Fail-closed, header-only authentication for remote MCP transports."""
import hmac
import os
import sqlite3
from pathlib import Path

from app.config import DATA_DIR


def _load_key() -> str:
    key = os.environ.get("PROFILESTACK_MCP_API_KEY", "")
    if not key:
        path = Path(os.environ.get("PROFILESTACK_MCP_API_KEY_FILE", DATA_DIR / "mcp-api-key"))
        try:
            key = path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return ""
    # Reject accidental empty/weak configuration; never fall back to public access.
    return key if len(key) >= 32 and key.isascii() and not any(c.isspace() for c in key) else ""


MCP_API_KEY = _load_key()


def resolve_mcp_principal(headers):
    authorization = headers.getlist("authorization")
    api_keys = headers.getlist("x-api-key")
    alt_api_keys = headers.getlist("api-key")

    # Ambiguous credentials from multiple distinct header sources are rejected.
    distinct_sources = [h for h in (authorization, api_keys, alt_api_keys) if h]
    if len(distinct_sources) > 1 or any(len(h) > 1 for h in distinct_sources):
        return None

    candidate = ""
    if authorization:
        raw = authorization[0].strip()
        if raw.lower().startswith("bearer "):
            candidate = raw[7:].strip()
        elif raw.startswith("psk_") or (bool(MCP_API_KEY) and hmac.compare_digest(raw, MCP_API_KEY)):
            candidate = raw
        else:
            return None
    elif api_keys:
        candidate = api_keys[0].strip()
    elif alt_api_keys:
        candidate = alt_api_keys[0].strip()

    if not candidate or not candidate.isascii():
        return None
    from app import api_key_store as store
    try:
        if candidate.startswith("psk_"):
            return store.get_principal(candidate)
        if bool(MCP_API_KEY) and hmac.compare_digest(candidate, MCP_API_KEY) and store.legacy_enabled():
            from app.key_policy import ALL_PERMISSIONS
            return {'id': 'legacy', 'permissions': ALL_PERMISSIONS, 'profile_access': 'all', 'profiles': [], 'owner': 'Usmandevx', 'role': 'admin'}
        return None
    except (OSError, sqlite3.Error):
        # Storage failures never downgrade authentication to public access.
        return None


def valid_mcp_key(headers) -> bool:
    return resolve_mcp_principal(headers) is not None


def refresh_principal(principal):
    from app import api_key_store as store
    if not principal:
        return None
    if principal['id'] == 'legacy':
        return principal if MCP_API_KEY and store.legacy_enabled() else None
    return store.get_active_principal(principal['id'])


# Transport context is populated by the HTTP boundary; local stdio alone has None.
from contextvars import ContextVar
http_principal: ContextVar[dict | None] = ContextVar('mcp_http_principal', default=None)
