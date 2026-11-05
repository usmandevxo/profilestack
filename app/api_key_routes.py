"""User & Administrator credential management; MCP keys cannot manage other keys."""
from typing import Literal, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from app import api_key_store as store, auth_manager as auth
from app.mcp_auth import MCP_API_KEY
from app.key_policy import PERMISSIONS, DEFAULT_PERMISSIONS, validate_policy
from app import profile_manager as pm
from app import folder_manager as fm

router = APIRouter()


def require_auth(request: Request):
    # Never combine MCP credentials with web credential management.
    if request.headers.get("X-API-Key") or request.headers.get("Authorization"):
        raise HTTPException(403, "API credentials cannot access key management.")
    # Deliberately require the HttpOnly web cookie, not a key, URL token or bearer session.
    session = auth.validate_session(request.cookies.get(auth.COOKIE_NAME, ""))
    if not session:
        raise HTTPException(401, "Administrator login required.")
    users = auth.load_users()
    username = (session.get("username") or "").strip().lower()
    user = next((u for k, u in users.items() if k.lower() == username), None)
    if user and user.get("status") == "disabled":
        raise HTTPException(403, "Account is disabled.")
    if user and user.get("role") and user.get("role") not in ("admin", "user"):
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
    role = user.get("role", "admin") if user else ("admin" if username in ("admin", "usmandevx") else "user")
    session["role"] = role
    session["user"] = user
    return session


def require_admin(request: Request):
    session = require_auth(request)
    if session.get("role") != "admin":
        raise HTTPException(403, "Administrator access required.")
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
    profile_access: Literal['all', 'selected', 'group'] = 'selected'
    profiles: list[str] = Field(default_factory=list, max_length=5000)
    folders: list[str] = Field(default_factory=list, max_length=100)

    def checked(self, owner: Optional[str] = None):
        try:
            policy = validate_policy(self.permissions, self.profile_access, self.profiles, self.folders)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        if policy['profile_access'] == 'selected':
            available = {p['name'] for p in pm.list_profiles(owner=owner)}
            if set(policy['profiles']) - available:
                raise HTTPException(422, 'One or more selected profiles no longer exist. Refresh the profile list.')
        elif policy['profile_access'] == 'group':
            available_folders = {f['id'] for f in fm.load_folders(owner=owner)}
            if set(policy['folders']) - available_folders:
                raise HTTPException(422, 'One or more selected groups/folders no longer exist.')
        return policy


class KeyCreate(KeyName, KeyPolicy):
    expires_in_days: Literal[7, 30, 90] | None = 30
    owner: Optional[str] = None


def response(payload, status_code=200):
    return JSONResponse(payload, status_code=status_code, headers={"Cache-Control": "no-store", "Pragma": "no-cache", "Referrer-Policy": "no-referrer"})


@router.get("/api/api-keys")
async def list_api_keys(request: Request, session: dict = Depends(require_auth)):
    role = session.get("role", "user")
    caller_username = session.get("username", "admin")
    
    if role == "admin":
        target_owner = request.query_params.get("user")
        keys = store.list_keys(owner=target_owner) if target_owner else store.list_keys()
        available_profs = pm.list_profiles(owner=target_owner) if target_owner else pm.list_profiles()
        available_flds = fm.load_folders(owner=target_owner) if target_owner else fm.load_folders()
        enabled = store.legacy_enabled()
        legacy_info = {"id": "legacy", "name": "Legacy server key", "prefix": "Server-managed", "status": ("active" if enabled else "revoked") if MCP_API_KEY else "unavailable"}
        catalog = [{"id": k, "label": v[0], "group": v[1]} for k, v in PERMISSIONS.items()]
    else:
        target_owner = caller_username
        keys = store.list_keys(owner=target_owner)
        available_profs = pm.list_profiles(owner=target_owner)
        available_flds = fm.load_folders(owner=target_owner)
        legacy_info = {"id": "legacy", "name": "Legacy server key", "prefix": "Server-managed", "status": "unavailable"}
        user_obj = session.get("user", {})
        allowed_p = set(user_obj.get("mcp_access", {}).get("allowed_permissions", []))
        catalog = [{"id": k, "label": v[0], "group": v[1]} for k, v in PERMISSIONS.items() if k in allowed_p]

    return response({
        "permission_catalog": catalog,
        "available_profiles": [{"name": p["name"], "folder": p.get("folder", "default"), "owner": p.get("owner", "admin")} for p in available_profs],
        "available_folders": [{"id": f["id"], "name": f["name"], "color": f.get("color", "#64748b"), "owner": f.get("owner", "admin")} for f in available_flds],
        "keys": keys,
        "legacy": legacy_info,
        "endpoint": str(request.base_url).rstrip("/") + "/mcp/sse",
    })


@router.post("/api/api-keys", status_code=201)
async def create_api_key(body: KeyCreate, session: dict = Depends(require_auth)):
    role = session.get("role", "user")
    caller_username = session.get("username", "admin")

    if role == "admin":
        owner = (body.owner or caller_username).strip()
    else:
        owner = caller_username
        user_obj = session.get("user", {})
        allowed_perms = set(user_obj.get("mcp_access", {}).get("allowed_permissions", []))
        for p in body.permissions:
            if p not in allowed_perms:
                raise HTTPException(403, f"Permission '{p}' is not allowed for your MCP access profile.")

    policy_checked = body.checked(owner=owner)
    created = store.create_key(
        name=body.name,
        expires_in_days=body.expires_in_days,
        permissions=policy_checked["permissions"],
        profile_access=policy_checked["profile_access"],
        profiles=policy_checked["profiles"],
        folders=policy_checked["folders"],
        owner=owner,
    )
    return response(created, 201)


@router.patch("/api/api-keys/{key_id}/permissions")
async def edit_key_policy(key_id: str, body: KeyPolicy, session: dict = Depends(require_auth)):
    role = session.get("role", "user")
    caller_username = session.get("username", "admin")

    target_owner = None if role == "admin" else caller_username
    existing = store.get_key(key_id, owner=target_owner)
    if not existing:
        raise HTTPException(404, "API key not found.")

    owner = existing.get("owner", caller_username)
    if role != "admin":
        user_obj = session.get("user", {})
        allowed_perms = set(user_obj.get("mcp_access", {}).get("allowed_permissions", []))
        for p in body.permissions:
            if p not in allowed_perms:
                raise HTTPException(403, f"Permission '{p}' is not allowed for your MCP access profile.")

    policy_checked = body.checked(owner=owner)
    item = store.update_policy(
        key_id=key_id,
        permissions=policy_checked["permissions"],
        profile_access=policy_checked["profile_access"],
        profiles=policy_checked["profiles"],
        folders=policy_checked["folders"],
        owner=target_owner,
    )
    if item is None:
        raise HTTPException(404, "API key not found.")
    return response({"key": item})


@router.patch("/api/api-keys/{key_id}")
async def rename_api_key(key_id: str, body: KeyName, session: dict = Depends(require_auth)):
    role = session.get("role", "user")
    caller_username = session.get("username", "admin")
    target_owner = None if role == "admin" else caller_username

    item = store.rename_key(key_id, body.name, owner=target_owner)
    if item is None:
        raise HTTPException(404, "API key not found.")
    return response({"key": item})


@router.delete("/api/api-keys/{key_id}")
async def revoke_api_key(key_id: str, session: dict = Depends(require_auth)):
    role = session.get("role", "user")
    caller_username = session.get("username", "admin")

    if key_id == "legacy":
        if role != "admin":
            raise HTTPException(403, "Administrator access required.")
        store.revoke_legacy()
    else:
        target_owner = None if role == "admin" else caller_username
        if not store.revoke_key(key_id, owner=target_owner):
            raise HTTPException(404, "API key not found.")
    return response({"revoked": True})
