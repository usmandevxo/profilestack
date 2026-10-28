"""Fail-closed, header-only authentication for remote MCP transports."""
import hmac
import os
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


def valid_mcp_key(headers) -> bool:
    if not MCP_API_KEY:
        return False
    authorization = headers.getlist("authorization")
    api_keys = headers.getlist("x-api-key")
    # Ambiguous credentials are rejected, rather than selecting one silently.
    if len(authorization) > 1 or len(api_keys) > 1 or (authorization and api_keys):
        return False
    candidate = ""
    if authorization:
        scheme, separator, candidate = authorization[0].partition(" ")
        if not separator or scheme.lower() != "bearer":
            return False
    elif api_keys:
        candidate = api_keys[0]
    if not candidate or not candidate.isascii():
        return False
    return hmac.compare_digest(candidate, MCP_API_KEY)
