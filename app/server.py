import shutil
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
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

# Ensure default administrator user is initialized
auth.init_default_user()

app = FastAPI(title="ProfileStack", version="1.0.0", docs_url="/api/docs", redoc_url=None)

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
app.mount("/mcp", mcp.sse_app(transport_security=mcp_sec))

templates = Jinja2Templates(directory=str(templates_path))

PUBLIC_PREFIXES = (
    "/login",
    "/api/auth/login",
    "/static/",
    "/screenshots/",
    "/mcp",
    "/favicon.ico",
    "/favicon.svg",
    "/apple-touch-icon.png",
)


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if any(path == p or path.startswith(p) for p in PUBLIC_PREFIXES):
        return await call_next(request)

    token = request.cookies.get(auth.COOKIE_NAME)
    session = auth.validate_session(token) if token else None

    if session:
        request.state.user = session
        return await call_next(request)

    if path.startswith("/api/"):
        return JSONResponse(status_code=401, content={"detail": "Authentication required."})

    next_url = str(request.url.path)
    if request.url.query:
        next_url += f"?{request.url.query}"
    return RedirectResponse(url=f"/login?next={quote(next_url)}", status_code=303)


# Request Models
class LoginRequest(BaseModel):
    username: str
    password: str
    remember: Optional[bool] = True


class CreateFolderRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    color: Optional[str] = "#2563eb"
    id: Optional[str] = None


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


@app.get("/api/auth/me")
async def auth_me(request: Request):
    user = getattr(request.state, "user", None)
    if not user:
        token = request.cookies.get(auth.COOKIE_NAME)
        user = auth.validate_session(token) if token else None
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {"username": user["username"], "created_at": user.get("created_at")}


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
    if demo == "1" or request.query_params.get("demo") == "1" or name.startswith("chrome-sandbox"):
        dummy_p = next((p for p in DUMMY_PROFILES if p["name"] == name), DUMMY_PROFILES[0])
        user = getattr(request.state, "user", None)
        return templates.TemplateResponse(request=request, name="vnc.html", context={"profile": dummy_p, "user": user, "is_demo": True})
    profile = pm.get_profile(name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    user = getattr(request.state, "user", None)
    return templates.TemplateResponse(request=request, name="vnc.html", context={"profile": profile, "user": user, "is_demo": False})


# ── System Telemetry ──────────────────────────────────────────────────────────
@app.get("/api/telemetry")
async def get_telemetry(request: Request, demo: Optional[str] = None):
    if demo == "1" or request.query_params.get("demo") == "1":
        return DUMMY_TELEMETRY
    return pm.system_telemetry()


# ── Folders Management ────────────────────────────────────────────────────────
@app.get("/api/folders")
async def get_folders(request: Request, demo: Optional[str] = None):
    if demo == "1" or request.query_params.get("demo") == "1":
        return DUMMY_FOLDERS
    return fm.list_folders_with_stats()


@app.post("/api/folders")
async def create_folder(req: CreateFolderRequest):
    try:
        return fm.create_folder(
            name=req.name,
            description=req.description or "",
            color=req.color or "#2563eb",
            folder_id=req.id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/folders/{folder_id}")
async def update_folder(folder_id: str, req: UpdateFolderRequest):
    try:
        return fm.update_folder(
            folder_id=folder_id,
            name=req.name,
            description=req.description,
            color=req.color,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/folders/{folder_id}")
async def delete_folder(folder_id: str, move_to: Optional[str] = "default"):
    try:
        return fm.delete_folder(folder_id=folder_id, move_to=move_to or "default")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Profiles CRUD ─────────────────────────────────────────────────────────────
@app.get("/api/profiles")
async def get_profiles(request: Request, folder: Optional[str] = None, demo: Optional[str] = None):
    if demo == "1" or request.query_params.get("demo") == "1":
        if folder and folder != "all":
            return [p for p in DUMMY_PROFILES if p["folder"] == folder]
        return DUMMY_PROFILES
    return pm.list_profiles(folder_id=folder)


@app.get("/api/profiles/{name}")
async def get_profile(name: str):
    profile = pm.get_profile(name)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@app.post("/api/profiles")
async def create_profile(req: CreateProfileRequest):
    try:
        entry = pm.create_profile(
            name=req.name,
            folder=req.folder or "default",
            proxy=req.proxy,
            start_url=req.start_url,
            host_mount=req.host_mount,
            note=req.note,
        )
        return {"status": "success", "profile": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/profiles/{name}")
async def update_profile(name: str, req: UpdateProfileRequest):
    try:
        entry = pm.update_profile(
            name=name,
            folder=req.folder,
            proxy=req.proxy,
            start_url=req.start_url,
            host_mount=req.host_mount,
            note=req.note,
        )
        return {"status": "success", "profile": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/move-folder")
async def move_profile_folder(name: str, req: MoveProfileFolderRequest):
    try:
        return pm.move_profile_to_folder(name=name, target_folder=req.folder)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/profiles/{name}")
async def delete_profile(name: str):
    try:
        return pm.delete_profile(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Profile Lifecycle Actions ─────────────────────────────────────────────────
@app.post("/api/profiles/{name}/start")
async def start_profile(name: str):
    try:
        res = pm.start_profile(name)
        return res
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/stop")
async def stop_profile(name: str):
    try:
        return pm.stop_profile(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/restart")
async def restart_profile(name: str):
    try:
        return pm.restart_profile(name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Archive Export / Import ───────────────────────────────────────────────────
@app.get("/api/profiles/{name}/export")
async def export_profile(name: str):
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
async def import_profile(file: UploadFile = File(...)):
    try:
        ARCHIVES_DIR.mkdir(parents=True, exist_ok=True)
        dest = ARCHIVES_DIR / file.filename
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        entry = am.import_profile_zip(dest)
        dest.unlink(missing_ok=True)
        return {"status": "success", "profile": entry}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
async def send_text(name: str, req: SendTextRequest):
    p = pm.get_profile(name)
    if not p or p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    try:
        return await cdp.send_text_input(int(p["cdp_port"]), req.text, req.press_enter or False)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/send-key")
async def send_key(name: str, req: SendKeyRequest):
    p = pm.get_profile(name)
    if not p or p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    try:
        return await cdp.send_key_event(int(p["cdp_port"]), req.key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/profiles/{name}/mouse-action")
async def mouse_action(name: str, req: MouseActionRequest):
    p = pm.get_profile(name)
    if not p or p.get("status") != "running" or not p.get("cdp_port"):
        raise HTTPException(status_code=400, detail="Profile is not currently running.")
    try:
        return await cdp.send_mouse_action(int(p["cdp_port"]), req.action)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
