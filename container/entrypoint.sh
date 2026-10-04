#!/bin/bash
set -e

PROFILE_NAME="${CHROME_PROFILE:-default}"
SCRIPT_DIR="/home/chrome/scripts"

source "$SCRIPT_DIR/hardware-spoof.sh"   "$PROFILE_NAME"
source "$SCRIPT_DIR/user-agent-spoof.sh" "$PROFILE_NAME"

export TZ="${CHROME_TIMEZONE:-UTC}"
export LANG="${CHROME_LANGUAGE//-/_}.UTF-8"
export LC_ALL="$LANG"

# Start virtual display (Xvfb)
RES="${CHROME_RESOLUTION:-1920x1080}"
Xvfb :99 -screen 0 "${RES}x24" -nolisten tcp -dpi 96 &
XVFB_PID=$!

export DISPLAY=:99

# Wait for X display
for _ in $(seq 1 30); do
    if xset q &>/dev/null; then
        break
    fi
    sleep 0.1
done

# Start lightweight window manager (Openbox)
if [ -f "$SCRIPT_DIR/openbox-rc.xml" ]; then
    openbox --config-file "$SCRIPT_DIR/openbox-rc.xml" &
else
    openbox &
fi

# Start local VNC server
x11vnc -display :99 -nopw -listen 127.0.0.1 -rfbport 5900 -shared -forever -quiet &

# Start Web VNC (noVNC bridge on port 6080)
websockify --web=/usr/share/novnc 6080 127.0.0.1:5900 &>/dev/null &

# Start CDP 0.0.0.0:9222 -> 127.0.0.1:9223 forwarder
python3 "$SCRIPT_DIR/cdp-forwarder.py" &

# Start proxy auth wrapper if authenticated proxy is configured
if [[ -n "${CHROME_PROXY_USER:-}" && -n "${CHROME_PROXY_HOST:-}" ]]; then
    python3 "$SCRIPT_DIR/proxy-wrapper.py" &
    for _ in $(seq 1 30); do
        if python3 -c "import socket; socket.create_connection(('127.0.0.1', 1081), 0.2).close()" 2>/dev/null; then
            break
        fi
        sleep 0.1
    done
fi

ACTUAL_CORES=$(nproc)
SPOOF_CORES=$(( CHROME_CPU_CORES < ACTUAL_CORES ? CHROME_CPU_CORES : ACTUAL_CORES ))
if [ "$SPOOF_CORES" -lt 1 ]; then
    SPOOF_CORES=1
fi

FLAGS=(
    "--remote-debugging-port=9223"
    "--remote-debugging-address=127.0.0.1"
    "--remote-allow-origins=*"
    "--no-sandbox"
    "--no-first-run"
    "--no-default-browser-check"
    "--disable-sync"
    "--disable-translate"
    "--disable-logging"
    "--log-level=3"
    "--disable-blink-features=AutomationControlled"
    "--disable-infobars"
    "--webrtc-ip-handling-policy=disable_non_proxied_udp"
    "--lang=$CHROME_LANGUAGE"
    "--user-agent=$CHROME_USER_AGENT"
    "--window-size=${RES/x/,}"
    "--window-position=0,0"
    "--start-maximized"
    "--disable-gpu"
    "--enable-software-rasterizer"
    "--disable-dev-shm-usage"
    "--user-data-dir=/home/chrome/.config/chromium"
    "--password-store=basic"
    "--disable-features=LockProfileCookieDatabase"
    "--disable-session-crashed-bubble"
    "--restore-last-session"
)

# Start URL
TARGET_URL="${CHROME_START_URL:-https://www.google.com}"

CONFIG_DIR="/home/chrome/.config/chromium"

# Clean stale Singleton locks and crash indicators from previous host runs
rm -f "$CONFIG_DIR/SingletonLock" "$CONFIG_DIR/SingletonCookie" "$CONFIG_DIR/SingletonSocket" 2>/dev/null || true
rm -f "$CONFIG_DIR/Default/LOCK" "$CONFIG_DIR/Default/SingletonLock" 2>/dev/null || true

# Ensure persistent machine-id per profile across container restarts
MACHINE_ID_FILE="$CONFIG_DIR/machine-id"
if [ ! -f "$MACHINE_ID_FILE" ]; then
    python3 -c "import hashlib, sys; print(hashlib.md5(('profilestack_' + sys.argv[1]).encode()).hexdigest())" "$PROFILE_NAME" > "$MACHINE_ID_FILE" 2>/dev/null || true
fi
STABLE_ID="$(cat "$MACHINE_ID_FILE" 2>/dev/null || true)"
if [ -n "$STABLE_ID" ]; then
    echo "$STABLE_ID" > /etc/machine-id 2>/dev/null || true
    echo "$STABLE_ID" > /var/lib/dbus/machine-id 2>/dev/null || true
fi

# Ensure session restore and cookie retention are permanently set in Preferences
mkdir -p "$CONFIG_DIR/Default"
python3 -c "
import json, os
pref_path = '$CONFIG_DIR/Default/Preferences'
try:
    data = {}
    if os.path.exists(pref_path):
        with open(pref_path, 'r') as f:
            data = json.load(f)
    prof = data.setdefault('profile', {})
    prof['exit_type'] = 'Normal'
    prof['exited_cleanly'] = True
    prof.setdefault('default_content_setting_values', {})['cookies'] = 1
    prof['cookie_controls_mode'] = 0
    # Enable session restore so session cookies (login auth tokens) are NEVER wiped on exit
    sess = data.setdefault('session', {})
    sess['restore_on_startup'] = 1
    with open(pref_path, 'w') as f:
        json.dump(data, f, indent=2)
except Exception:
    pass
" 2>/dev/null || true

# Set CPU affinity for process tree
taskset -p -c "0-$((SPOOF_CORES-1))" $$ &>/dev/null || true

# Execute Chromium directly so Docker SIGTERM signals trigger graceful SQLite & session flush
if [ -f "$CONFIG_DIR/Default/Preferences" ] && [ -d "$CONFIG_DIR/Default/Sessions" ]; then
    exec chromium-browser "${FLAGS[@]}" "$@"
else
    exec chromium-browser "${FLAGS[@]}" "$@" "$TARGET_URL"
fi
