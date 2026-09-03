# ProfileStack

> Self-hosted, lightweight anti-detect browser cluster fusing Docker containment, hardware fingerprint spoofing, WebRTC defense, proxy routing, and Model Context Protocol (MCP 2.x) automation.

![ProfileStack Brand](app/static/img/logo-full.svg)

[![Documentation](https://img.shields.io/badge/Docs-Complete_Guide-blue.svg)](docs/GUIDE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP 2.x](https://img.shields.io/badge/MCP-2.x_Ready-emerald.svg)](docs/GUIDE.md#9-model-context-protocol-mcp-2x-integration)

---

## Complete Guide

For in-depth architectural blueprints, aaPanel deployment, Nginx proxy rules, MCP 2.x tool specs, and operator runbooks, read the **[ProfileStack Complete Operator & Developer Guide](docs/GUIDE.md)**.

---

## Screenshots

| Desktop Cluster Dashboard | Interactive Remote Viewer & Trackpad |
|:---:|:---:|
| [![Desktop Dashboard](docs/screenshots/02-dashboard-desktop.png)](docs/screenshots/02-dashboard-desktop.png) | [![Remote Viewer](docs/screenshots/04-viewer-trackpad.png)](docs/screenshots/04-viewer-trackpad.png) |
| **Profile Provisioning & Emulation Modal** | **Secure Administrator Login** |
| [![Profile Configuration](docs/screenshots/03-create-profile-modal.png)](docs/screenshots/03-create-profile-modal.png) | [![Login Screen](docs/screenshots/01-login-screen.png)](docs/screenshots/01-login-screen.png) |

---

## Overview

ProfileStack is an open-source, server-native browser orchestration platform designed for multi-accounting, sandboxed automation, localized QA, and web crawling without triggering bot defense mechanisms.

Unlike resource-heavy desktop alternatives, ProfileStack runs on low-cost headless VPS instances (ARM64 and x86_64) using an ultra-minimal Alpine Linux container stack, kiosk Openbox window management (~3 MB RAM), and zero-CPU idle resource management.

---

## Key Features

- **Dockerized Browser Isolation:** Each profile operates in an unprivileged, sandboxed Docker container with isolated filesystems, dedicated memory limits, and isolated network namespaces.
- **Hardware & Fingerprint Spoofing:** Dynamic CPU core affinity (`taskset`), randomized canvas noise, consistent WebGL vendor/renderer emulation, and hardware signature masking.
- **WebRTC & Network Defense:** Prevents real IP leaks by routing all browser traffic through local SOCKS5/HTTP loopback authentication proxies with RFC 1929 support.
- **Model Context Protocol (MCP 2.x):** Native agentic AI control with 24 dedicated tools accessible via Server-Sent Events (`/mcp/sse`) and stdio transport (`profilestack-mcp`).
- **Interactive HTML5 Remote Viewer:** Built-in noVNC integration with virtual keyboard injection and a high-precision multi-touch trackpad with gesture recognition, vertical scroll strips, and sensitivity scaling.
- **Hierarchical Folder Structure:** Group and partition browser profiles physically on disk and logically within the dashboard.
- **Enterprise Session Security:** PBKDF2-HMAC-SHA256 password hashing (100,000 iterations), encrypted session cookies, and API route guards.

---

## Architecture

```
ProfileStack Host (FastAPI + Uvicorn :7800)
├── Nginx Reverse Proxy (SSL / WebSocket / Stream)
├── MCP Server (SSE & Stdio Transports)
└── Docker Engine SDK
    ├── Profile Container 1 (Alpine 3.19 + Chromium)
    │   ├── Xvfb (:99) + Openbox Kiosk
    │   ├── x11vnc + Websockify (:6080 -> :6201)
    │   ├── CDP Forwarder (:9222 -> :9223)
    │   └── Local Proxy Wrapper (:1081)
    └── Profile Container N...
```

---

## Quick Start

### Prerequisites

- Linux (Ubuntu 22.04+ / Debian 12 / Oracle Linux, ARM64 or x86_64)
- Docker Engine 24.0+
- Python 3.11+
- Nginx or aaPanel reverse proxy

### Installation

```bash
git clone git@github.com:usmandevxo/profilestack.git
cd profilestack

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build base container image
docker build -t profilestack-chrome:latest container/
```

### Running the Server

```bash
uvicorn app.server:app --host 127.0.0.1 --port 7800 --workers 2
```

### Default Credentials

Upon first launch, ProfileStack provisions a local administrator account:
- **Username:** `admin`
- **Password:** `admin`

Passwords are automatically hashed using PBKDF2-HMAC-SHA256 (100,000 rounds) and stored securely in `data/users.json`.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
