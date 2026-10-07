#!/usr/bin/env bash
set -e

SERVER_URL="https://profilestack.apanel.eu.cc"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
CONF_DIR="$HOME/.config/profilestack"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo "=========================================================="
echo "      ProfileStack Local Native Launcher Setup            "
echo "=========================================================="
echo ""

if ! command -v python3 &>/dev/null; then
    echo "[!] Error: Python 3 is required. Please install python3 first."
    exit 1
fi

mkdir -p "$BIN_DIR" "$APP_DIR" "$CONF_DIR" "$SYSTEMD_USER_DIR"

LAUNCHER_SCRIPT="$BIN_DIR/profilestack-launcher"

echo "[*] Downloading latest profilestack-launcher..."
curl -fsSL "$SERVER_URL/launcher/profilestack-launcher.py" -o "$LAUNCHER_SCRIPT"
chmod +x "$LAUNCHER_SCRIPT"

# 1. Register Desktop Protocol Handler (profilestack://)
DESKTOP_FILE="$APP_DIR/profilestack.desktop"
echo "[*] Registering system protocol handler (profilestack://)..."
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=ProfileStack Launcher
Comment=Launch ProfileStack anti-detect profiles in native desktop Chromium
Exec=$LAUNCHER_SCRIPT %u
Type=Application
Terminal=false
MimeType=x-scheme-handler/profilestack;
Categories=Network;WebBrowser;
EOF
chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi
if command -v xdg-mime &>/dev/null; then
    xdg-mime default profilestack.desktop x-scheme-handler/profilestack 2>/dev/null || true
fi

# 2. Setup user systemd service for zero-prompt background daemon
echo "[*] Configuring local companion service (systemd user daemon)..."
cat <<EOF > "$SYSTEMD_USER_DIR/profilestack-launcher.service"
[Unit]
Description=ProfileStack Local Companion Daemon
After=network.target

[Service]
ExecStart=$LAUNCHER_SCRIPT daemon
Restart=always
RestartSec=3

[Install]
WantedBy=default.target
EOF

if command -v systemctl &>/dev/null; then
    systemctl --user daemon-reload 2>/dev/null || true
    systemctl --user enable --now profilestack-launcher.service 2>/dev/null || true
    echo "[+] Local daemon started on http://127.0.0.1:7890"
fi

# Verify Chromium presence
HAS_CHROME=0
for b in chromium google-chrome-stable google-chrome brave-bin brave microsoft-edge-stable vivaldi ungoogled-chromium; do
    if command -v "$b" &>/dev/null; then
        HAS_CHROME=1
        echo "[+] Found Chromium binary: $(command -v "$b")"
        break
    fi
done

if [ "$HAS_CHROME" -eq 0 ]; then
    echo ""
    echo "=========================================================="
    echo "[!] ACTION REQUIRED: Chromium is not installed yet."
    echo "    ProfileStack requires a Chromium-based browser."
    echo "    Install it on CachyOS / Arch by running:"
    echo "        sudo pacman -S chromium"
    echo "=========================================================="
    echo ""
fi

# Ensure ~/.local/bin is in PATH hint
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "[i] Tip: Add ~/.local/bin to your PATH in ~/.bashrc or ~/.zshrc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "=========================================================="
echo "[+] SUCCESS: ProfileStack Launcher is ready!"
echo "=========================================================="
echo "Binary:           $LAUNCHER_SCRIPT"
echo "Protocol handler: profilestack:// is active"
echo "Daemon:           Listening on 127.0.0.1:7890"
echo ""
echo "You can now click 'Real Browser' in the ProfileStack web UI"
echo "to launch 100% native desktop Chromium windows!"
echo "=========================================================="
