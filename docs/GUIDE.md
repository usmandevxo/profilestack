# ProfileStack: Complete Operator & Developer Guide

> The definitive guide to deploying, orchestrating, and automating self-hosted anti-detect browser clusters with Docker, Model Context Protocol (MCP 2.x), and low-latency HTML5 streaming.

![ProfileStack Brand](../app/static/img/logo-full.svg)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Visual Tour & Screenshots](#2-visual-tour--screenshots)
3. [Server Deployment Runbook](#3-server-deployment-runbook)
4. [Authentication & Security](#4-authentication--security)
5. [Browser Profile Management](#5-browser-profile-management)
6. [Stealth, Hardware & Proxy Spoofing](#6-stealth-hardware--proxy-spoofing)
7. [Interactive Remote Viewer (Trackpad & Keyboard)](#7-interactive-remote-viewer-trackpad--keyboard)
8. [Hierarchical Folder Organization](#8-hierarchical-folder-organization)
9. [Model Context Protocol (MCP 2.x) Integration](#9-model-context-protocol-mcp-2x-integration)
10. [REST API Reference](#10-rest-api-reference)
11. [Production Systemd & aaPanel Operations](#11-production-systemd--aapanel-operations)
12. [Troubleshooting & FAQs](#12-troubleshooting--faqs)

---

## 1. Architecture Overview

ProfileStack is an enterprise-grade, self-hosted anti-detect browser cluster built specifically for low-resource headless Linux environments (ARM64 and x86_64).

Traditional anti-detect solutions (Multilogin, GoLogin, AdsPower) rely on bloated Electron desktop applications or heavy virtual machines. ProfileStack completely decouples the browser container from the desktop:

```
[ Incoming HTTPS / WSS Traffic ]
              │
              ▼
   ┌───────────────────────────────────────────────┐
   │ Nginx Reverse Proxy (SSL / WebSocket Upgrade) │
   └───────────────────────┬───────────────────────┘
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
┌─────────────────────────┐ ┌──────────────────────────────────────┐
│ FastAPI Backend (:7800) │ │ Dynamic Stream Proxy (/vnc-stream/) │
│  - Auth Engine (PBKDF2) │ └──────────────────┬───────────────────┘
│  - Profile Registry     │                    │
│  - Docker Engine SDK    │                    │ (Direct WebSocket)
│  - MCP 2.x Server (:SSE)│                    │
└────────────┬────────────┘                    │
             │                                 │
             ▼                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ Isolated Profile Container (Alpine 3.19 + Chromium)             │
│  ├── Xvfb (:99) Display Server                                   │
│  ├── Openbox Kiosk Window Manager (~3 MB RAM, Zero Titlebars)    │
│  ├── x11vnc Server (:5900)                                       │
│  ├── Websockify (:6080 -> Host Dynamic Port :6201+)              │
│  ├── CDP Forwarder (:9222 -> :9223 Host Dynamic Port :9401+)     │
│  ├── Local RFC 1929 SOCKS5 Proxy Wrapper (:1081)                 │
│  └── Chromium Headless/GUI with Hardware & User-Agent Spoofing   │
└──────────────────────────────────────────────────────────────────┘
```

### Key Technical Pillars

1. **Ultra-Minimal Footprint:** Idle profiles consume **0% CPU and 0 MB RAM**. Active running containers use a stripped Openbox kiosk window manager consuming under 3 MB of RAM, leaving maximum system resources for Chromium.
2. **Containerized Process Isolation:** Each browser profile runs inside an isolated Alpine Linux Docker container with dedicated memory and CPU constraints.
3. **Loopback CDP Bridging:** Solves Chromium's internal restriction against non-localhost DevTools connections via a high-performance Python loopback forwarder (`cdp-forwarder.py`).
4. **Hardware & Network Spoofing:** Dynamic CPU core affinity (`taskset`), randomized canvas noise, consistent WebGL vendor/renderer emulation, and RFC 1929 authenticated SOCKS5 proxy loopback routing.

---

## 2. Visual Tour & Screenshots

### 2.1 Responsive Login Portal
The authentication gate is protected by PBKDF2-HMAC-SHA256 password hashing (100,000 rounds) and persistent HttpOnly session cookies. Default credentials (`admin` / `admin`) are provisioned automatically.

![Login Screen](screenshots/01-login-screen.png)

---

### 2.2 Cluster Overview (Desktop Dashboard)
The desktop command center features live 4-card telemetry (Active Profiles, Total Profiles, Cluster RAM, Disk Footprint), physical folder navigation, live status pills, and instant container action buttons.

![Dashboard Desktop](screenshots/02-dashboard-desktop.png)

---

### 2.3 Profile Provisioning & Hardware Emulation
The desktop modal interface allows rapid profile creation with folder partitioning, proxy protocol selection (Direct, SOCKS5, HTTP), startup URL configuration, and automated hardware spoofing setup.

![Profile Configuration](screenshots/03-create-profile-modal.png)

---

### 2.4 Interactive Remote Viewer (Touch Trackpad & Virtual Keyboard)
A zero-latency HTML5 browser streaming interface featuring a hardware-style multi-touch trackpad, live cursor coordinate HUD, tactile vertical scroll strip, 1-finger gestures, Drag Lock, and virtual keyboard injection.

![Remote Viewer](screenshots/04-viewer-trackpad.png)

---

## 3. Server Deployment Runbook

### Prerequisites
- OS: Ubuntu 22.04 LTS / 24.04 LTS, Debian 12, or Oracle Linux 9 (ARM64 or x86_64)
- CPU: 2+ vCPUs recommended
- RAM: 4 GB+ (runs 2–4 concurrent profiles), 8 GB+ (runs 6–8 concurrent profiles)
- Storage: 20 GB+ NVMe/SSD
- Docker: Engine 24.0+
- Python: Python 3.11+ or 3.12+

### Step 1: Clone Repository
```bash
git clone git@github.com:usmandevxo/profilestack.git /www/wwwroot/profilestack
cd /www/wwwroot/profilestack
```

### Step 2: Initialize Virtual Environment & Dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Build Base Docker Image
```bash
docker build -t profilestack-chrome:latest container/
```

### Step 4: Configure Nginx Reverse Proxy
Deploy an Nginx server block with WebSocket upgrade directives and path-preserving VNC stream forwarding:

```nginx
server {
    listen 80;
    listen 443 ssl http2;
    server_name profilestack.yourdomain.com;

    ssl_certificate /path/to/fullchain.pem;
    ssl_certificate_key /path/to/privkey.pem;

    # Dynamic VNC Stream WebSocket Proxy (preserves path & query args)
    location ~ ^/vnc-stream/(?<vnc_port>[0-9]+)/(?<vnc_path>.*)$ {
        proxy_pass http://127.0.0.1:$vnc_port/$vnc_path$is_args$args;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400s;
        proxy_send_timeout 86400s;
    }

    # Model Context Protocol (MCP) Server-Sent Events
    location /mcp/ {
        proxy_pass http://127.0.0.1:7800;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 86400s;
    }

    # Primary Web Application & APIs
    location / {
        proxy_pass http://127.0.0.1:7800;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 4. Authentication & Security

### Default Administrator Account
* **Username:** `admin`
* **Password:** `admin`

### Security Specifications
1. **Password Hashing:** PBKDF2-HMAC-SHA256 with 100,000 iterations and cryptographically random 16-byte salts.
2. **Session Cookies:** 30-day persistent HttpOnly cookies (`ps_session`), immune to XSS access.
3. **API Guards:** REST endpoints reject unauthorized calls with `HTTP 401 Unauthorized`.
4. **Auto-Redirect:** Frontend fetch interceptor automatically bounces expired sessions back to `/login?next=...`.
5. **MCP Exemption:** Machine-to-machine AI agent endpoints (`/mcp`) bypass interactive cookie guards.

---

## 5. Browser Profile Management

### 5.1 Profile Storage Layout
Profiles are organized physically on disk under partitioned folder paths:
```text
/www/wwwroot/profilestack/data/profiles/
├── default/
├── automation/
│   └── chrome-sandbox-us1/
└── ad-verify/
    └── ad-compliance-eu/
```

### 5.2 Starting a Profile
1. Locate the target profile in the cluster dashboard.
2. Click **Start Profile**.
3. ProfileStack dynamically:
   - Allocates unused VNC (range 6201–6299) and CDP (range 9401–9499) host ports.
   - Generates/reads `hardware-signature.json`.
   - Boots the unprivileged container, mounts the profile volume, and initializes the display.
   - Transitions state to **Running** within 1.2 seconds.

### 5.3 Stopping a Profile
Click **Stop** to issue a graceful `SIGTERM` to the container. The Docker Engine halts the container and releases port bindings, dropping CPU and RAM usage to 0.

### 5.4 Archiving & Backups
Click **Export ZIP** to download a compressed archive of any profile. ProfileStack automatically excludes volatile caches (Chromium shader caches, crash dumps, and transient cache files) to keep archives lightweight.

---

## 6. Stealth, Hardware & Proxy Spoofing

### Hardware Fingerprint Randomization
Each profile container executes `container/hardware-spoof.sh` before Chromium launches:
- **CPU Cores:** Emulates custom core counts via Linux `taskset` CPU affinity.
- **RAM Limits:** Overrides `navigator.deviceMemory` reporting.
- **Screen Geometry:** Injects realistic window dimensions and color depth.
- **WebGL Emulation:** Masks SwiftShader/Mesa signatures with real Intel/NVIDIA/Apple GPU vendor strings.

### Authenticated Proxy Routing
Chromium does not natively support inline username/password authentication for SOCKS5 proxies. ProfileStack solves this with `container/proxy-wrapper.py`:
- Listens locally on `127.0.0.1:1081`.
- Handles RFC 1929 authentication handshakes transparently.
- Chromium connects to `socks5://127.0.0.1:1081` with zero authentication prompts.
- WebRTC traffic is strictly locked to the proxy route, eliminating IP leakage.

---

## 7. Interactive Remote Viewer (Trackpad & Keyboard)

When opening `https://profilestack.yourdomain.com/viewer/<profile_name>`, the viewer offers full control:

### 7.1 Multi-Touch Trackpad
- **Smooth Pointer Movement:** 1-finger sliding across the trackpad surface translates directly into RFB mouse movements with sub-pixel interpolation.
- **Live Coordinate HUD:** Real-time $X, Y$ coordinate display in the trackpad header.
- **Click Gestures:** 1-finger tap performs a Left Click; rapid double-tap performs a Double Click.
- **Tactile Vertical Scroll Strip:** Dedicated right-hand scroll gutter with `▲` and `▼` directional notches for natural web scrolling.
- **Physical Mouse Buttons:** Dedicated Left (50%), Middle (20%), and Right (30%) buttons.
- **Drag Lock:** Toggle Drag Lock to effortlessly drag tabs, scrollbars, or canvas elements without holding down buttons.
- **Sensitivity Scaling:** Adjustable speed slider from `0.75x` (fine precision) to `2.0x` (fast desktop traversal).

### 7.2 On-Screen Virtual Keyboard
- Toggle the keyboard drawer via the top bar or toolbar button.
- Type custom phrases and click **Send Text** to inject keystrokes directly into Chromium.
- Hardware navigation buttons: `Enter`, `Tab`, `Backspace`, `Escape`, and arrow keys (`▲`, `▼`, `◄`, `►`).

---

## 8. Hierarchical Folder Organization

Profiles can be grouped by project, client, or workflow (e.g. `E-Commerce`, `Social Media`, `Marketplaces`):

1. **Creating Folders:** Click `+` in the sidebar or use `POST /api/folders`. Choose a folder name and hex color tag.
2. **Dynamic Migration:** Move profiles across folders via the UI or `POST /api/profiles/{name}/move-folder`. ProfileStack moves the container directory on disk, updates path pointers, and re-binds mounts seamlessly.
3. **Filtering:** Click any folder in the left sidebar or mobile dropdown to filter the active view instantly.

---

## 9. Model Context Protocol (MCP 2.x) Integration

ProfileStack provides first-class support for AI agent orchestration through the official Model Context Protocol.

### 9.1 Connection Endpoints
- **Server-Sent Events (SSE):** `https://profilestack.yourdomain.com/mcp/sse`
- **Messages Route:** `https://profilestack.yourdomain.com/mcp/messages/`
- **Local Stdio Executable:** `/usr/local/bin/profilestack-mcp`

### 9.2 Complete Tool Catalog (24 Tools)

| Tool Name | Scope | Description |
|---|---|---|
| `list_profiles` | Cluster | List all profiles with status, ports, and proxies |
| `get_profile` | Cluster | Get full details and resource utilization for a profile |
| `create_profile` | Cluster | Provision a new profile with proxy and folder assignments |
| `update_profile` | Cluster | Modify profile settings, proxy URL, or startup parameters |
| `delete_profile` | Cluster | Permanently remove a profile and delete its data |
| `start_profile` | Lifecycle | Boot container and initialize VNC/CDP streaming |
| `stop_profile` | Lifecycle | Halt container and release port allocations |
| `restart_profile` | Lifecycle | Gracefully restart an active container |
| `get_system_telemetry` | Telemetry | Host and container CPU, RAM, and disk utilization |
| `list_proxies` | Proxies | List configured proxy servers |
| `add_proxy` | Proxies | Register a proxy server in the catalog |
| `test_proxy` | Proxies | Measure latency and verify external IP of a proxy |
| `delete_proxy` | Proxies | Remove a proxy from the catalog |
| `list_folders` | Folders | List all organizational folders and profile counts |
| `create_folder` | Folders | Create a new organizational folder |
| `update_folder` | Folders | Modify folder name or hex color tag |
| `delete_folder` | Folders | Delete folder and reassign profiles to default |
| `move_profile_to_folder` | Folders | Migrate profile disk files to a new folder |
| `cdp_navigate` | Automation | Navigate browser to target URL |
| `cdp_click` | Automation | Click a DOM element by CSS selector |
| `cdp_type` | Automation | Type text into an active input field |
| `cdp_evaluate` | Automation | Execute arbitrary JavaScript inside the page context |
| `cdp_screenshot` | Automation | Capture full-page or viewport PNG screenshot |
| `cdp_get_content` | Automation | Extract page title and full DOM HTML content |

### 9.3 Client Configuration (Claude Desktop, Cursor, Hermes)
Add ProfileStack to your MCP configuration file (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "profilestack": {
      "command": "/www/wwwroot/profilestack/.venv/bin/python3",
      "args": ["/www/wwwroot/profilestack/app/mcp_server.py"]
    }
  }
}
```

---

## 10. REST API Reference

### Profile Management

#### `GET /api/profiles`
Returns all registered browser profiles. Optional filter: `?folder=<folder_id>`.

#### `POST /api/profiles`
Create a new browser profile.
```json
{
  "name": "amazon-buyer-1",
  "folder": "marketplaces",
  "start_url": "https://www.amazon.com",
  "proxy": "socks5://user:pass@1.2.3.4:1080",
  "note": "Primary purchasing account"
}
```

#### `POST /api/profiles/{name}/start`
Starts the container for the profile and returns assigned VNC and CDP ports:
```json
{
  "status": "started",
  "name": "amazon-buyer-1",
  "vnc_port": 6202,
  "cdp_port": 9402
}
```

#### `POST /api/profiles/{name}/stop`
Stops the profile container.

#### `POST /api/profiles/{name}/move-folder`
Migrate a profile to another organizational folder:
```json
{
  "folder": "scraping-bots"
}
```

---

## 11. Production Systemd & aaPanel Operations

ProfileStack is managed as a standard Linux systemd daemon (`profilestack.service`).

### Service Controls
```bash
# Check service status
sudo systemctl status profilestack.service

# Restart service
sudo systemctl restart profilestack.service

# View live application logs
sudo journalctl -u profilestack.service -f -n 50
```

### aaPanel Integration
ProfileStack is registered in the aaPanel SQLite database (`/www/server/panel/data/default.db`, Site ID 13). You can configure SSL certificates, Nginx reverse proxy directives, and domain bindings directly inside the aaPanel Web GUI.

---

## 12. Troubleshooting & FAQs

### Q: Why does the VNC screen show a black window?
**A:** Chromium is launching or the target webpage is loading. If it persists, ensure your host has sufficient shared memory (`/dev/shm`). ProfileStack automatically runs containers with `--shm-size=512m` to avoid Chromium render crashes.

### Q: Can I run ProfileStack on ARM64 Oracle Cloud VPS?
**A:** Yes. The base Alpine Dockerfile and all Python dependencies are verified and compiled natively for `aarch64`.

### Q: How do I change the admin password?
**A:** Run the interactive password updater:
```bash
env -u PYTHONPATH /www/wwwroot/profilestack/.venv/bin/python3 -c "
from app import auth_manager
auth_manager.init_default_user('admin', 'YourNewPasswordHere')
print('Password updated successfully.')
"
sudo systemctl restart profilestack.service
```

---

## License

MIT License. Copyright (c) 2026 Usman Khalid.
