"""Administrator-only credential management; MCP keys cannot manage other keys."""
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app import api_key_store as store, auth_manager as auth
from app.mcp_auth import MCP_API_KEY
from app.key_policy import PERMISSIONS, DEFAULT_PERMISSIONS, validate_policy
from app import profile_manager as pm

router = APIRouter()


def require_admin(request: Request):
    # Never combine MCP credentials with administrator credential management.
    if request.headers.get("X-API-Key") or request.headers.get("Authorization"):
        raise HTTPException(403, "API credentials cannot access key management.")
    # Deliberately require the HttpOnly web cookie, not a key, URL token or bearer session.
    session = auth.validate_session(request.cookies.get(auth.COOKIE_NAME, ""))
    if not session:
        raise HTTPException(401, "Administrator login required.")
    users = auth.load_users()
    username = (session.get("username") or "").strip().lower()
    user = next((u for k, u in users.items() if k.lower() == username), None)
    if user and user.get("role") and user.get("role") != "admin":
        raise HTTPException(403, "Administrator access required.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-origin request denied.")
    origin = request.headers.get("origin")
    if origin:
        source = urlsplit(origin)
        if source.scheme not in ("http", "https") or source.netloc != request.url.netloc:
            raise HTTPException(403, "Cross-origin request denied.")
    if request.method not in ("GET", "HEAD"):
        if request.headers.get("X-ProfileStack-Management") != "1":
            raise HTTPException(403, "Management request header required.")
    return session


class KeyName(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Enter a key name without control characters.")
        return value


class KeyPolicy(BaseModel):
    permissions: list[str] = Field(default_factory=lambda: list(DEFAULT_PERMISSIONS), max_length=50)
    profile_access: Literal['all', 'selected'] = 'selected'
    profiles: list[str] = Field(default_factory=list, max_length=5000)

    def checked(self):
        try:
            policy = validate_policy(self.permissions, self.profile_access, self.profiles)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        available = {p['name'] for p in pm.list_profiles()}
        if set(policy['profiles']) - available:
            raise HTTPException(422, 'One or more selected profiles no longer exist. Refresh the profile list.')
        return policy


class KeyCreate(KeyName, KeyPolicy):
    expires_in_days: Literal[7, 30, 90] | None = 30


def response(payload, status_code=200):
    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})


@router.get("/api/api-keys", dependencies=[Depends(require_admin)])
async def list_api_keys(request: Request):
    enabled = store.legacy_enabled()
    return response({"permission_catalog": [{"id": k, "label": v[0], "group": v[1]} for k, v in PERMISSIONS.items()], "available_profiles": [{"name": p["name"], "folder": p.get("folder", "default")} for p in pm.list_profiles()], "keys": store.list_keys(), "legacy": {"id": "legacy", "name": "Legacy server key", "prefix": "Server-managed", "status": ("active" if enabled else "revoked") if MCP_API_KEY else "unavailable"}, "endpoint": str(request.base_url).rstrip("/") + "/mcp/sse"})


@router.post("/api/api-keys", status_code=201, dependencies=[Depends(require_admin)])
async def create_api_key(body: KeyCreate):
    return response(store.create_key(body.name, body.expires_in_days, **body.checked()), 201)


@router.patch("/api/api-keys/{key_id}/permissions", dependencies=[Depends(require_admin)])
async def edit_key_policy(key_id: str, body: KeyPolicy):
    item = store.update_policy(key_id, **body.checked())
    if item is None:
        raise HTTPException(404, 'API key not found.')
    return response({'key': item})


@router.patch("/api/api-keys/{key_id}", dependencies=[Depends(require_admin)])
async def rename_api_key(key_id: str, body: KeyName):
    item = store.rename_key(key_id, body.name)
    if item is None:
        raise HTTPException(404, "API key not found.")
    return response({"key": item})


@router.delete("/api/api-keys/{key_id}", dependencies=[Depends(require_admin)])
async def revoke_api_key(key_id: str):
    if key_id == "legacy":
        store.revoke_legacy()
    elif not store.revoke_key(key_id):
        raise HTTPException(404, "API key not found.")
    return response({"revoked": True})
