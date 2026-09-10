#!/bin/bash
# hardware-spoof.sh - ProfileStack stable per-profile machine fingerprint.
PROFILE_NAME="${1:-default}"
CONFIG_DIR="${CHROME_CONFIG_DIR:-/home/chrome/.config/chromium}"
HARDWARE_FILE="$CONFIG_DIR/hardware-signature.json"
mkdir -p "$CONFIG_DIR"

read -r CHROME_CPU_CORES CHROME_RESOLUTION CHROME_TIMEZONE CHROME_LANGUAGE CHROME_GPU_MODE <<< "$(python3 - "$PROFILE_NAME" "$HARDWARE_FILE" <<'PYEOF'
import json, os, random, sys

profile, path = sys.argv[1], sys.argv[2]

RESOLUTIONS = ["1920x1080", "2560x1440", "1440x900", "1600x900"]
TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "Europe/London", "Europe/Berlin", "Europe/Paris", "Asia/Tokyo", "Asia/Karachi",
    "Asia/Dubai", "Asia/Kolkata", "Asia/Singapore", "Australia/Sydney"
]
LANGUAGES = [
    "en-US", "en-GB", "en-CA", "en-AU", "de-DE", "fr-FR", "es-ES", "it-IT"
]
GPU_MODES = ["swiftshader", "swiftshader", "vulkan"]

data = {}
if os.path.exists(path):
    try:
        with open(path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        data = {}

data.setdefault("profile", profile)
hw = data.setdefault("hardware", {})
sys_ = data.setdefault("system", {})
br = data.setdefault("browser", {})

if "cpu_cores" not in hw:
    hw["cpu_cores"] = random.choice([4, 6, 8, 12, 16])
if "screen_resolution" not in hw:
    hw["screen_resolution"] = random.choice(RESOLUTIONS)
if "timezone" not in sys_:
    sys_["timezone"] = random.choice(TIMEZONES)
if "language" not in br:
    br["language"] = random.choice(LANGUAGES)
if "gpu_mode" not in br:
    br["gpu_mode"] = random.choice(GPU_MODES)

with open(path, "w") as f:
    json.dump(data, f, indent=2)

print(hw["cpu_cores"], hw["screen_resolution"], sys_["timezone"], br["language"], br["gpu_mode"])
PYEOF
)"

export CHROME_CPU_CORES CHROME_RESOLUTION CHROME_TIMEZONE CHROME_LANGUAGE CHROME_GPU_MODE
