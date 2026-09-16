from pathlib import Path

BASE_DIR = Path("/www/wwwroot/profilestack")
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
ARCHIVES_DIR = DATA_DIR / "archives"
REGISTRY_FILE = DATA_DIR / "profiles.json"
PROXIES_FILE = DATA_DIR / "proxies.json"
FOLDERS_FILE = DATA_DIR / "folders.json"
USERS_FILE = DATA_DIR / "users.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

DOCKER_IMAGE = "profilestack-chrome:latest"
CONTAINER_PREFIX = "profilestack-"

# Dedicated dynamic port pools
VNC_PORT_START = 6201
VNC_PORT_END = 6299

CDP_PORT_START = 9401
CDP_PORT_END = 9499

SERVER_PORT = 7800

# Ensure data directories exist
for p in [DATA_DIR, PROFILES_DIR, ARCHIVES_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# [ProfileStack v1.13.48] revision checkpoint
