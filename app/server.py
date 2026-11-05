import shutil
import time
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional

from app.config import ARCHIVES_DIR, BASE_DIR
from app.mcp_server import mcp, SCREENSHOTS_DIR
from mcp.server.transport_security import TransportSecuritySettings
import app.profile_manager as pm
import app.proxy_manager as prm
import app.archive_manager as am
import app.cdp_client as cdp
import app.folder_manager as fm
import app.auth_manager as auth
from app.mcp_auth import valid_mcp_key, resolve_mcp_principal, http_principal
from app.api_key_routes import router as api_key_router, require_admin, require_auth
from app.validator import validate_proxy_url

# Ensure default administrator user is initialized
auth.init_default_user()

app = FastAPI(title="ProfileStack", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_path = BASE_DIR / "app" / "static"
templates_path = BASE_DIR / "app" / "templates"

mcp_sec = TransportSecuritySettings(enable_dns_rebinding_protection=False)

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")
from app.mcp_transport import KeyBoundSSE
app.mount("/mcp", KeyBoundSSE(mcp.sse_app(transport_security=mcp_sec)))

templates = Jinja2Templates(directory=str(templates_path))
app.include_router(api_key_router)


@app.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request):
    user = require_auth(request)
    response = templates.TemplateResponse(request=request, name="api_keys.html", context={"user": user})
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    user = require_admin(request)
    response = templates.TemplateResponse(request=request, name="users.html", context={"user": user})
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response

PUBLIC_PREFIXES = (
    "/login",
    "/api/auth/login",
    "/favicon.ico",
    "/favicon.svg",
    "/apple-touch-icon.png",
)


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        request = Request(scope, receive=receive)
        path = request.url.path

        # StaticFiles normalizes dot segments; reject them before prefix auth checks.
        if any(part in (".", "..") for part in path.split("/")) or "\\" in path:
            response = JSONResponse(status_code=400, content={"detail": "Invalid path"}, headers={"Cache-Control": "no-store"})
            return await response(scope, receive, send)

        if path == "/mcp" or path.startswith("/mcp/"):
            principal = resolve_mcp_principal(request.headers)
            if principal is None:
                response = JSONResponse(
                    status_code=401,
                    content={"detail": "Unauthorized"},
                    headers={"WWW-Authenticate": "Bearer", "Cache-Control": "no-store"},
                )
                return await response(scope, receive, send)

            scope.setdefault("state", {})["mcp_principal"] = principal
            token = http_principal.set(principal)

            async def send_with_headers(message):
                if message["type"] == "http.response.start":
                    headers = [(k, v) for k, v in message.get("headers", []) if k.lower() not in (b"cache-control", b"referrer-policy")]
                    headers.append((b"cache-control", b"no-store"))
                    headers.append((b"referrer-policy", b"no-referrer"))
                    message["headers"] = headers
                await send(message)

            try:
                return await self.app(scope, receive, send_with_headers)
            finally:
                http_principal.reset(token)

        public_asset = path in {
            "/static/apple-touch-icon.png", "/static/favicon.ico", "/static/favicon.svg",
            "/static/favicon.png", "/static/favicon-16x16.png", "/static/favicon-32x32.png",
        } or any(path.startswith(prefix) for prefix in ("/static/css/", "/static/js/", "/static/img/"))
        if public_asset or any(path == p or (p.endswith("/") and path.startswith(p)) for p in PUBLIC_PREFIXES):
            return await self.app(scope, receive, send)

        token = request.cookies.get(auth.COOKIE_NAME)
        if not token:
            token = request.headers.get("X-Session-Token") or request.query_params.get("token")
            if not token:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:].strip()

        session = auth.validate_session(token) if token else None
        if session:
            uname = str(session.get("username") or "")
            user_obj = auth.get_user(uname)
            if user_obj and user_obj.get("status") == "disabled":
                if token:
                    auth.destroy_session(token)
                if path.startswith("/api/"):
                    response = JSONResponse(status_code=401, content={"detail": "Account is disabled."})
                    return await response(scope, receive, send)
                response = RedirectResponse(url="/login", status_code=303)
                return await response(scope, receive, send)
            if user_obj:
                session["role"] = user_obj.get("role", "user")
                session["mcp_profile"] = user_obj.get("mcp_profile", "standard")
                session["mcp_access"] = user_obj.get("mcp_access", {})
            else:
                session.setdefault("role", "admin" if uname.lower() in ("admin", "usmandevx") else "user")
                session.setdefault("mcp_profile", "full" if session["role"] == "admin" else "standard")
                session.setdefault("mcp_access", {})
            scope.setdefault("state", {})["user"] = session
            return await self.app(scope, receive, send)

        if path.startswith("/api/") and path != "/api/docs":
            response = JSONResponse(status_code=401, content={"detail": "Authentication required."})
            return await response(scope, receive, send)

        next_url = str(request.url.path)
        if request.url.query:
            next_url += f"?{request.url.query}"
        response = RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)
        return await response(scope, receive, send)


app.add_middleware(AuthMiddleware)


# Request Models
class LoginRequest(BaseModel):
    username: str
    password: str
    remember: Optional[bool] = True


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: Optional[str] = "user"
    status: Optional[str] = "active"
    mcp_profile: Optional[str] = "standard"
    mcp_access: Optional[dict] = None
    notes: Optional[str] = ""
    assigned_proxy: Optional[str] = None


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None
    mcp_profile: Optional[str] = None
    mcp_access: Optional[dict] = None
    notes: Optional[str] = None
    assigned_proxy: Optional[str] = None


class SetUserProxyRequest(BaseModel):
    proxy: Optional[str] = ""


class ResetPasswordRequest(BaseModel):
    password: Optional[str] = None
    new_password: Optional[str] = None
    newPassword: Optional[str] = None

    def get_password(self) -> str:
        pwd = self.new_password or self.password or self.newPassword
        if not pwd or len(pwd) < 5:
            raise ValueError("New password must be at least 5 characters.")
        return pwd


class CreateFolderRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#2563eb"
    id: Optional[str] = None
    owner: Optional[str] = None


class UpdateFolderRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class MoveProfileFolderRequest(BaseModel):
    folder: str


class CreateProfileRequest(BaseModel):
    name: str
    folder: Optional[str] = "default"
    proxy: Optional[str] = ""
    start_url: Optional[str] = ""
    host_mount: Optional[str] = ""
    note: Optional[str] = ""
    owner: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    folder: Optional[str] = None
    proxy: Optional[str] = None
    start_url: Optional[str] = None
    host_mount: Optional[str] = None
    note: Optional[str] = None


class ProxyRequest(BaseModel):
    name: str
    url: str
    note: Optional[str] = ""


class TestProxyRequest(BaseModel):
    url: str


class SendTextRequest(BaseModel):
    text: str
    press_enter: Optional[bool] = False


class SendKeyRequest(BaseModel):
    key: str


class MouseActionRequest(BaseModel):
    action: str


class SendShortcutRequest(BaseModel):
    modifiers: list  # e.g. ["Control"], ["Control", "Shift"]
    key: str         # e.g. "c", "v", "F5"


class PasteClipboardRequest(BaseModel):
    text: str        # clipboard text read by the browser, forwarded here for CDP injection


# ── Frontend Views ─────────────────────────────────────────────────────────────
@app.api_route("/favicon.ico", methods=["GET", "HEAD"], include_in_schema=False)
async def favicon_ico():
    return FileResponse(static_path / "favicon.ico", media_type="image/x-icon")


@app.api_route("/favicon.svg", methods=["GET", "HEAD"], include_in_schema=False)
async def favicon_svg():
    return FileResponse(static_path / "favicon.svg", media_type="image/svg+xml")


@app.api_route("/apple-touch-icon.png", methods=["GET", "HEAD"], include_in_schema=False)
async def apple_touch_icon():
    return FileResponse(static_path / "apple-touch-icon.png", media_type="image/png")


@app.api_route("/login", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def login_page(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token and auth.validate_session(token):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(request=request, name="login.html")


@app.post("/api/auth/login")
async def login_api(req: LoginRequest, request: Request):
    user = auth.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    ip = request.client.host if request.client else ""
    ua = request.headers.get("user-agent", "")
    token = auth.create_session(username=user["username"], ip_address=ip, user_agent=ua)

    max_age = auth.SESSION_DURATION_SECONDS if req.remember else None
    response = JSONResponse(content={"status": "success", "username": user["username"]})
    response.set_cookie(
        key=auth.COOKIE_NAME,
        value=token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@app.api_route("/logout", methods=["GET", "POST"])
async def logout_view(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        auth.destroy_session(token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key=auth.COOKIE_NAME, path="/")
    return response


@app.get("/api/auth/check", include_in_schema=False)
async def auth_check():
    """Minimal response for Nginx auth_request; middleware validates the session."""
    return JSONResponse(content={"authenticated": True}, headers={"Cache-Control": "no-store"})


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = getattr(request.state, "user", None)
    token = request.cookies.get(auth.COOKIE_NAME)
    if not user and token:
        user = auth.validate_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    uname = str(user.get("username") or "")
    user_record = auth.get_user(uname)
    return {
        "username": uname,
        "role": user_record.get("role", "user") if user_record else "user",
        "status": user_record.get("status", "active") if user_record else "active",
        "mcp_profile": user_record.get("mcp_profile", "standard") if user_record else "standard",
        "mcp_access": user_record.get("mcp_access", {}) if user_record else {},
        "token": token or "",
        "created_at": user.get("created_at"),
    }


# ── Demo / Showcase Dummy Data ────────────────────────────────────────────────
DUMMY_FOLDERS = [
    {"id": "default", "name": "General", "color": "#64748b", "total_profiles": 0},
    {"id": "automation", "name": "Automation & AI", "color": "#2563eb", "total_profiles": 1},
    {"id": "ad-verify", "name": "Ad Verification", "color": "#059669", "total_profiles": 1},
    {"id": "ecommerce", "name": "E-Commerce", "color": "#7c3aed", "total_profiles": 1},
    {"id": "market-research", "name": "Market Research", "color": "#d97706", "total_profiles": 1},
]

DUMMY_PROFILES = [
    {
        "name": "chrome-sandbox-us1",
        "folder": "automation",
        "folder_name": "Automation & AI",
        "folder_color": "#2563eb",
        "status": "running",
        "vnc_port": 6201,
        "cdp_port": 9401,
        "proxy": "socks5://residential-node.proxy-network.io:1080",
        "start_url": "https://github.com/explore",
        "note": "Autonomous browser orchestration agent node",
        "size_mb": 42.8,
        "created_at": "2026-09-18 10:20:15",
        "machine": {
            "cpu_cores": 4,
            "screen_resolution": "1920x1080",
            "timezone": "America/New_York",
            "language": "en-US",
        },
    },
    {
        "name": "ad-compliance-eu",
        "folder": "ad-verify",
        "folder_name": "Ad Verification",
        "folder_color": "#059669",
        "status": "running",
        "vnc_port": 6202,
        "cdp_port": 9402,
        "proxy": "http://uk-secure.bright-node.net:8080",
        "start_url": "https://www.google.com/search?q=cloud+infrastructure",
        "note": "Localized compliance verification worker",
        "size_mb": 38.2,
        "created_at": "2026-09-24 14:12:08",
        "machine": {
            "cpu_cores": 2,
            "screen_resolution": "1440x900",
            "timezone": "Europe/London",
            "language": "en-GB",
        },
    },
    {
        "name": "marketplace-tester",
        "folder": "ecommerce",
        "folder_name": "E-Commerce",
        "folder_color": "#7c3aed",
        "status": "stopped",
        "vnc_port": None,
        "cdp_port": None,
        "proxy": "",
        "start_url": "https://www.amazon.com/",
        "note": "Synthetic buyer journey testing cohort",
        "size_mb": 56.1,
        "created_at": "2026-09-28 09:45:30",
        "machine": {
            "cpu_cores": 4,
            "screen_resolution": "1920x1080",
            "timezone": "America/Chicago",
            "language": "en-US",
        },
    },
    {
        "name": "seo-cohort-bot",
        "folder": "market-research",
        "folder_name": "Market Research",
        "folder_color": "#d97706",
        "status": "stopped",
        "vnc_port": None,
        "cdp_port": None,
        "proxy": "socks5://datacenter-exit.proxies.net:9050",
        "start_url": "https://en.wikipedia.org/wiki/Web_scraping",
        "note": "Scheduled SERP rank indexation monitor",
        "size_mb": 29.4,
        "created_at": "2026-10-01 16:30:22",
        "machine": {
            "cpu_cores": 2,
            "screen_resolution": "1366x768",
            "timezone": "UTC",
            "language": "en-US",
        },
    },
]

DUMMY_TELEMETRY = {
    "total_profiles": 4,
    "running_profiles": 2,
    "ram_used_gb": 3.8,
    "ram_total_gb": 24.0,
    "storage_profiles_mb": 166.5,
    "memory_used_gb": 3.8,
    "memory_total_gb": 24.0,
    "profiles_storage_mb": 166.5,
    "cpu_percent": 4.2,
    "ram_percent": 15.8,
    "disk_total_gb": 100.0,
    "disk_used_gb": 18.4,
    "disk_percent": 18.4,
}


@app.api_route("/", methods=["GET", "HEAD"], response_class=HTMLResponse)
async def index_view(request: Request):
    user = getattr(request.state, "user", None)
    return templates.TemplateResponse(request=request, name="index.html", context={"user": user})


@app.get("/viewer/{name}", response_class=HTMLResponse)
async def viewer_view(request: Request, name: str, demo: Optional[str] = None):
    user = getattr(request.state, "user", None)
    if demo == "1" or request.query_params.get("demo") == "1" or name.startswith("chrome-sandbox"):
        dummy_p = next((p for p in DUMMY_PROFILES if p["name"] == name), DUMMY_PROFILES[0])
        return templates.TemplateResponse(request=request, name="vnc.html", context={"profile": dummy_p, "user": user, "is_demo": True})
    owner = None if (user and user.get("role") == "admin") else ((user.get("username") or "admin") if user else "admin")
    profile = pm.get_profile(name, owner=owner)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found or access denied")
    return templates.TemplateResponse(request=request, name="vnc.html", context={"profile": profile, "user": user, "is_demo": False})


# ── User Management REST APIs (Admin Only) ────────────────────────────────────
@app.get("/api/users")
async def get_users_list(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    users = auth.list_users(is_admin=True)
    all_profiles = pm.list_profiles()
    all_folders = fm.load_folders()
    from app import api_key_store as store
    all_keys = store.list_keys()

    for u in users:
        uname = (u.get("username") or "").lower()
        u["profile_count"] = sum(1 for p in all_profiles if (p.get("owner") or "admin").lower() == uname)
        u["folder_count"] = sum(1 for f in all_folders if (f.get("owner") or "admin").lower() == uname)
        u["key_count"] = sum(1 for k in all_keys if (k.get("owner") or "admin").lower() == uname)
    return users


@app.post("/api/users", status_code=201)
async def create_user_endpoint(req: CreateUserRequest, request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    try:
        created = auth.create_user(
            username=req.username,
            password=req.password,
            role=req.role or "user",
            status=req.status or "active",
            mcp_profile=req.mcp_profile or "standard",
            mcp_access=req.mcp_access,
            notes=req.notes or "",
            assigned_proxy=req.assigned_proxy,
        )
        fm.get_user_default_folder(created["username"])
        return {"status": "success", "user": created}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users-presets")
async def get_users_presets_endpoint(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    from app.key_policy import ALL_PERMISSIONS
    return {
        "presets": auth.DEFAULT_MCP_PRESETS,
        "all_permissions": ALL_PERMISSIONS,
    }


@app.get("/api/users/{username}")
async def get_user_detail(username: str, request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    is_admin = user.get("role") == "admin"
    is_self = str(user.get("username") or "").lower() == username.lower()
    if not (is_admin or is_self):
        raise HTTPException(status_code=403, detail="Access denied.")
    u = auth.get_user(username, is_admin=is_admin)
    if not u:
        raise HTTPException(status_code=404, detail="User not found.")
    res = dict(u)
    res.pop("password_hash", None)
    res.pop("salt", None)
    if not is_admin:
        res.pop("assigned_proxy", None)
    return res


@app.put("/api/users/{username}")
async def update_user_endpoint(username: str, req: UpdateUserRequest, request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    try:
        updated = auth.update_user(
            username=username,
            role=req.role,
            status=req.status,
            mcp_profile=req.mcp_profile,
            mcp_access=req.mcp_access,
            notes=req.notes,
            assigned_proxy=req.assigned_proxy,
        )
        return {"status": "success", "user": updated}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/users/{username}/proxy")
@app.put("/api/users/{username}/proxy")
async def set_user_proxy_endpoint(username: str, req: SetUserProxyRequest, request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    proxy_val = (req.proxy or "").strip()
    if proxy_val:
        try:
            from app.proxy_manager import resolve_proxy_url
            resolved = resolve_proxy_url(proxy_val)
            if not resolved:
                raise ValueError("Could not resolve proxy.")
            if resolved == proxy_val:
                validate_proxy_url(proxy_val)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid proxy format: {e}")
    try:
        updated = auth.set_user_proxy(username, proxy_val)
        return {
            "status": "success",
            "username": username,
            "assigned_proxy": proxy_val,
            "user": updated,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/users/{username}/proxy")
async def clear_user_proxy_endpoint(username: str, request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    try:
        updated = auth.set_user_proxy(username, "")
        return {
            "status": "success",
            "username": username,
            "assigned_proxy": "",
            "user": updated,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/users/{username}/reset-password")
async def reset_user_password_endpoint(username: str, req: ResetPasswordRequest, request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    caller_role = user.get("role", "user")
    caller_name = str(user.get("username") or "")

    # Admin can reset any user's password; standard user can reset their own password
    if caller_role != "admin" and caller_name.lower() != username.strip().lower():
        raise HTTPException(status_code=403, detail="Administrator access required.")
    try:
        new_pwd = req.get_password()
        current_token = request.cookies.get("ps_session")
        auth.admin_reset_password(username, new_pwd, preserve_token=current_token)
        return {"status": "success", "message": f"Password reset for user '{username}'."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/reset-password")
async def auth_self_reset_password_endpoint(req: ResetPasswordRequest, request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    username = str(user.get("username") or "")
    try:
        new_pwd = req.get_password()
        current_token = request.cookies.get("ps_session")
        auth.admin_reset_password(username, new_pwd, preserve_token=current_token)
        return {"status": "success", "message": f"Password updated for '{username}'."}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/users/{username}")
async def delete_user_endpoint(username: str, request: Request, reassign_to: Optional[str] = None):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Administrator access required.")
    if str(user.get("username") or "").lower() == username.lower():
        raise HTTPException(status_code=400, detail="Cannot delete your own administrator account.")
    try:
        auth.delete_user(username, current_username=user.get("username"), reassign_to=reassign_to)
        return {"status": "success", "deleted": username, "reassigned_to": reassign_to}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── System Telemetry ──────────────────────────────────────────────────────────
@app.get("/api/telemetry")
async def get_telemetry(request: Request, demo: Optional[str] = None):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"

    if demo == "1" or request.query_params.get("demo") == "1":
        if not is_admin:
            return {
                "total_profiles": DUMMY_TELEMETRY.get("total_profiles", 0),
                "running_profiles": DUMMY_TELEMETRY.get("running_profiles", 0),
            }
        return DUMMY_TELEMETRY

    if not is_admin:
        owner = user.get("username", "") if user else ""
        return pm.system_telemetry(owner=owner)

    return pm.system_telemetry(owner=None)


# ── Folders Management ────────────────────────────────────────────────────────
@app.get("/api/folders")
async def get_folders(request: Request, demo: Optional[str] = None):
    if demo == "1" or request.query_params.get("demo") == "1":
        return DUMMY_FOLDERS
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None
    if is_admin:
        requested_user = request.query_params.get("user")
        if requested_user:
            owner = requested_user.strip()
    else:
        owner = user.get("username", "admin") if user else "admin"
    return fm.list_folders_with_stats(owner=owner)


@app.post("/api/folders")
async def create_folder(req: CreateFolderRequest, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = req.owner.strip() if (is_admin and req.owner) else (user.get("username", "admin") if user else "admin")
    try:
        return fm.create_folder(
            name=req.name,
            description=req.description or "",
            color=req.color or "#2563eb",
            folder_id=req.id,
            owner=owner,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/folders/{folder_id}")
async def update_folder(folder_id: str, req: UpdateFolderRequest, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        return fm.update_folder(
            folder_id=folder_id,
            name=req.name,
            description=req.description,
            color=req.color,
            owner=owner,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/folders/{folder_id}")
async def delete_folder(folder_id: str, request: Request, move_to: Optional[str] = "default"):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        return fm.delete_folder(folder_id=folder_id, move_to=move_to or "default", owner=owner)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Profiles CRUD ─────────────────────────────────────────────────────────────
@app.get("/api/profiles")
async def get_profiles(request: Request, folder: Optional[str] = None, demo: Optional[str] = None):
    if demo == "1" or request.query_params.get("demo") == "1":
        if folder and folder != "all":
            return [p for p in DUMMY_PROFILES if p["folder"] == folder]
        return DUMMY_PROFILES
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None
    if is_admin:
        requested_user = request.query_params.get("user")
        if requested_user:
            owner = requested_user.strip()
    else:
        owner = user.get("username", "admin") if user else "admin"
    return pm.list_profiles(folder_id=folder, owner=owner)


@app.get("/api/profiles/{name}")
async def get_profile(name: str, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    profile = pm.get_profile(name, owner=owner)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found or access denied")
    return profile


@app.post("/api/profiles")
async def create_profile(req: CreateProfileRequest, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = req.owner.strip() if (is_admin and req.owner) else (user.get("username", "admin") if user else "admin")

    if not is_admin and user:
        uname = user.get("username", "")
        user_record = auth.get_user(uname)
        max_profiles = user_record.get("mcp_access", {}).get("max_profiles", 0) if user_record else 0
        if max_profiles > 0:
            existing_count = len(pm.list_profiles(owner=uname))
            if existing_count >= max_profiles:
                raise HTTPException(status_code=403, detail=f"Profile quota reached ({max_profiles} maximum profiles allowed).")

    try:
        entry = pm.create_profile(
            name=req.name,
            folder=req.folder or "default",
            proxy=req.proxy,
            start_url=req.start_url,
            host_mount=req.host_mount,
            note=req.note,
            owner=owner,
        )
        return {"status": "success", "profile": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/profiles/{name}")
async def update_profile(name: str, req: UpdateProfileRequest, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        entry = pm.update_profile(
            name=name,
            folder=req.folder,
            proxy=req.proxy,
            start_url=req.start_url,
            host_mount=req.host_mount,
            note=req.note,
            owner=owner,
        )
        return {"status": "success", "profile": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/move-folder")
async def move_profile_folder(name: str, req: MoveProfileFolderRequest, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        return pm.move_profile_to_folder(name=name, target_folder=req.folder, owner=owner)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/profiles/{name}")
async def delete_profile(name: str, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        return pm.delete_profile(name, owner=owner)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Profile Lifecycle Actions ─────────────────────────────────────────────────
@app.post("/api/profiles/{name}/start")
async def start_profile(name: str, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        res = pm.start_profile(name, owner=owner)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/stop")
async def stop_profile(name: str, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        return pm.stop_profile(name, owner=owner)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/restart")
async def restart_profile(name: str, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    try:
        return pm.restart_profile(name, owner=owner)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Archive Export / Import ───────────────────────────────────────────────────
@app.get("/api/profiles/{name}/export")
async def export_profile(name: str, request: Request):
    user = getattr(request.state, "user", None)
    is_admin = user and user.get("role") == "admin"
    owner = None if is_admin else (user.get("username", "admin") if user else "admin")
    profile = pm.get_profile(name, owner=owner)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found or access denied")
    try:
        zip_path = am.export_profile_zip(name)
        return FileResponse(
            path=str(zip_path),
            filename=f"{name}.zip",
            media_type="application/zip",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/import")
async def import_profile(request: Request, file: UploadFile = File(...)):
    user = getattr(request.state, "user", None)
    owner = (user.get("username", "admin") if user else "admin")
    try:
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        dest = ARCHIVES_DIR / file.filename
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        entry = am.import_profile_zip(dest, owner=owner)
        dest.unlink(missing_ok=True)
        return {"status": "success", "profile": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/sync-back")
async def sync_back_profile(name: str, file: UploadFile = File(...)):
    try:
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        dest = ARCHIVES_DIR / f"{name}_sync_{int(time.time())}.zip"
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = am.sync_back_profile_zip(name, dest)
        dest.unlink(missing_ok=True)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    return JSONResponse(get_openapi(title="ProfileStack", version="1.0.0", routes=app.routes))


@app.get("/api/docs", include_in_schema=False)
async def get_documentation(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        return RedirectResponse(url="/login?next=/api/docs", status_code=303)
    if user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    return get_swagger_ui_html(openapi_url="/openapi.json", title="ProfileStack - API Docs")


@app.get("/install-launcher.sh")
async def get_install_launcher_script(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    script_path = BASE_DIR / "launcher" / "install-launcher.sh"
    if not script_path.is_file():
        raise HTTPException(status_code=404, detail="Install script not found.")
    return FileResponse(path=str(script_path), media_type="text/x-shellscript", filename="install-launcher.sh")


@app.get("/install-desktop.sh")
async def get_install_desktop_script(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    script_path = BASE_DIR / "launcher" / "install-desktop.sh"
    if not script_path.is_file():
        raise HTTPException(status_code=404, detail="Install desktop script not found.")
    return FileResponse(path=str(script_path), media_type="text/x-shellscript", filename="install-desktop.sh")


@app.get("/launcher/profilestack-launcher.py")
async def get_launcher_binary(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    bin_path = BASE_DIR / "launcher" / "profilestack-launcher.py"
    if not bin_path.is_file():
        raise HTTPException(status_code=404, detail="Launcher binary not found.")
    return FileResponse(path=str(bin_path), media_type="text/x-python", filename="profilestack-launcher.py")


@app.get("/launcher/profilestack-desktop.py")
async def get_desktop_binary(request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    bin_path = BASE_DIR / "launcher" / "profilestack-desktop.py"
    if not bin_path.is_file():
        raise HTTPException(status_code=404, detail="Desktop binary not found.")
    return FileResponse(path=str(bin_path), media_type="text/x-python", filename="profilestack-desktop.py")


@app.get("/launcher/dist/{filename}")
async def get_launcher_dist_file(filename: str, request: Request):
    user = getattr(request.state, "user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=404, detail="Not Found")
    dist_path = (BASE_DIR / "launcher" / "dist" / filename).resolve()
    base_dist = (BASE_DIR / "launcher" / "dist").resolve()
    if not str(dist_path).startswith(str(base_dist)) or not dist_path.is_file():
        raise HTTPException(status_code=404, detail="Binary file not found.")
    return FileResponse(path=str(dist_path), media_type="application/octet-stream", filename=filename)


# ── Global Proxy Store ────────────────────────────────────────────────────────
@app.get("/api/proxies")
async def get_proxies():
    return prm.list_proxies()


@app.post("/api/proxies")
async def add_proxy(req: ProxyRequest):
    try:
        return prm.add_proxy(req.name, req.url, req.note or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/proxies/{name}")
async def delete_proxy(name: str):
    try:
        return prm.delete_proxy(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/proxies/test")
async def test_proxy(req: TestProxyRequest):
    try:
        return await prm.test_proxy(req.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Virtual Input & Touch Emulation ───────────────────────────────────────────
@app.post("/api/profiles/{name}/send-text")
async def send_text(name: str, req: SendTextRequest, request: Request):
    user = getattr(request.state, "user", None)
    owner = None if (user and user.get("role") == "admin") else (user.get("username", "admin") if user else "admin")
    p = pm.get_profile(name, owner=owner)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found or access denied.")
    if p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    try:
        return await cdp.send_text_input(int(p["cdp_port"]), req.text, req.press_enter or False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/send-key")
async def send_key(name: str, req: SendKeyRequest, request: Request):
    user = getattr(request.state, "user", None)
    owner = None if (user and user.get("role") == "admin") else (user.get("username", "admin") if user else "admin")
    p = pm.get_profile(name, owner=owner)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found or access denied.")
    if p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    try:
        return await cdp.send_key_event(int(p["cdp_port"]), req.key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/mouse-action")
async def mouse_action(name: str, req: MouseActionRequest, request: Request):
    user = getattr(request.state, "user", None)
    owner = None if (user and user.get("role") == "admin") else (user.get("username", "admin") if user else "admin")
    p = pm.get_profile(name, owner=owner)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found or access denied.")
    if p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    try:
        return await cdp.send_mouse_action(int(p["cdp_port"]), req.action)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/send-shortcut")
async def send_shortcut(name: str, req: SendShortcutRequest, request: Request):
    user = getattr(request.state, "user", None)
    owner = None if (user and user.get("role") == "admin") else (user.get("username", "admin") if user else "admin")
    p = pm.get_profile(name, owner=owner)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found or access denied.")
    if p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    if not req.key:
        raise HTTPException(status_code=400, detail="key is required.")
    try:
        return await cdp.send_shortcut(int(p["cdp_port"]), req.modifiers or [], req.key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/paste-clipboard")
async def paste_clipboard(name: str, req: PasteClipboardRequest, request: Request):
    user = getattr(request.state, "user", None)
    owner = None if (user and user.get("role") == "admin") else (user.get("username", "admin") if user else "admin")
    p = pm.get_profile(name, owner=owner)
    if not p:
        raise HTTPException(status_code=404, detail="Profile not found or access denied.")
    if p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    if not req.text:
        return {"status": "empty", "length": 0}
    try:
        return await cdp.paste_clipboard_text(int(p["cdp_port"]), req.text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
