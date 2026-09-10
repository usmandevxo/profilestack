#!/bin/bash
# user-agent-spoof.sh - Generates stable per-profile user-agent string
PROFILE_NAME="${1:-default}"
CONFIG_DIR="/home/chrome/.config/chromium"
UA_FILE="$CONFIG_DIR/user-agent.txt"
mkdir -p "$CONFIG_DIR"

if [[ ! -f "$UA_FILE" ]]; then
    CHROME_VERSION="$(chromium-browser --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+' | head -n1)"
    if [[ -z "$CHROME_VERSION" ]]; then
        CHROME_VERSION="124.0.6367.78"
    fi
    USER_AGENT="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/$CHROME_VERSION Safari/537.36"
    echo "$USER_AGENT" > "$UA_FILE"
fi

export CHROME_USER_AGENT="$(cat "$UA_FILE")"
