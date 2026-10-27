#!/usr/bin/env bash
set -e

SERVER_URL="https://profilestack.apanel.eu.cc"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
CONF_DIR="$HOME/ProfileStack/config"
PROFILES_DIR="$HOME/ProfileStack/profiles"

echo "=========================================================="
echo "    ProfileStack Desktop Application Installer (Native)   "
echo "=========================================================="
echo ""

if ! command -v python3 &>/dev/null; then
    echo "[!] Error: Python 3 is required. Please install python3 first."
    exit 1
fi

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR" "$CONF_DIR" "$PROFILES_DIR"

DESKTOP_SCRIPT="$BIN_DIR/profilestack-desktop"

echo "[*] Downloading ProfileStack Desktop client binary..."
curl -fsSL -A "Mozilla/5.0 ProfileStack/1.0" "$SERVER_URL/launcher/profilestack-desktop.py" -o "$DESKTOP_SCRIPT"
chmod +x "$DESKTOP_SCRIPT"

echo "[*] Downloading high-resolution SVG icon..."
curl -fsSL -A "Mozilla/5.0 ProfileStack/1.0" "$SERVER_URL/static/img/logo.svg" -o "$ICON_DIR/profilestack.svg" || true

# Register Desktop Entry (.desktop)
DESKTOP_FILE="$APP_DIR/profilestack-desktop.desktop"
echo "[*] Creating Desktop application entry..."
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=ProfileStack Desktop
Comment=ProfileStack Anti-Detect Browser Client - Native Chrome Profiles
Exec=$DESKTOP_SCRIPT %u
Icon=profilestack
Terminal=false
Type=Application
Categories=Network;WebBrowser;Development;
StartupWMClass=ProfileStackDesktop
MimeType=x-scheme-handler/profilestack;
EOF
chmod +x "$DESKTOP_FILE"

# Register protocol and update databases
if command -v update-desktop-database &>/dev/null; then
    update-desktop-database "$APP_DIR" 2>/dev/null || true
fi
if command -v xdg-mime &>/dev/null; then
    xdg-mime default profilestack-desktop.desktop x-scheme-handler/profilestack 2>/dev/null || true
fi
if command -v gtk-update-icon-cache &>/dev/null; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
fi

# Check for Chromium binary on system
HAS_CHROME=0
for b in chromium google-chrome-stable google-chrome brave-bin brave microsoft-edge-stable vivaldi ungoogled-chromium; do
    if command -v "$b" &>/dev/null; then
        HAS_CHROME=1
        echo "[+] Found native Chromium engine: $(command -v "$b")"
        break
    fi
done

if [ "$HAS_CHROME" -eq 0 ]; then
    echo ""
    echo "=========================================================="
    echo "[!] ATTENTION: Chromium browser engine is not installed."
    echo "    ProfileStack requires native Chromium to open profiles."
    echo "    Install it now:"
    echo "      On CachyOS / Arch: sudo pacman -S chromium"
    echo "      On Ubuntu / Debian: sudo apt install chromium-browser"
    echo "=========================================================="
    echo ""
fi

# Ensure ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo "[i] Tip: Add ~/.local/bin to your PATH in ~/.bashrc or ~/.zshrc:"
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "=========================================================="
echo "[+] SUCCESS: ProfileStack Desktop is installed!"
echo "=========================================================="
echo "Executable:       $DESKTOP_SCRIPT"
echo "Application Menu: ProfileStack Desktop"
echo "Launch Command:   profilestack-desktop"
echo ""
echo "You can launch 'ProfileStack Desktop' from your application"
echo "menu or by typing 'profilestack-desktop' in your terminal."
echo "No virtual display is used — profiles open directly in real"
echo "native desktop Chromium windows!"
echo "=========================================================="
