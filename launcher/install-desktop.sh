#!/usr/bin/env bash
# ProfileStack Desktop Installer for Linux (CachyOS, Arch, Ubuntu, Debian, Fedora)
set -e

SERVER_URL="https://profilestack.apanel.eu.cc"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
CONF_DIR="$HOME/ProfileStack/config"
PROFILES_DIR="$HOME/ProfileStack/profiles"
ARCH="$(uname -m)"

echo "=========================================================="
echo "    ProfileStack Desktop Linux Installer (Native Chrome)  "
echo "    Host Architecture: $ARCH                              "
echo "=========================================================="
echo ""

mkdir -p "$BIN_DIR" "$APP_DIR" "$ICON_DIR" "$CONF_DIR" "$PROFILES_DIR"

DESKTOP_SCRIPT="$BIN_DIR/profilestack-desktop"

# Check if pre-compiled binary is requested or available for this architecture
INSTALL_MODE="script"
for arg in "$@"; do
    if [ "$arg" == "--binary" ]; then
        INSTALL_MODE="binary"
    fi
done

if [ "$INSTALL_MODE" == "binary" ]; then
    echo "[*] Downloading pre-compiled standalone Linux ELF binary ($ARCH)..."
    if curl -fsSL -A "Mozilla/5.0 ProfileStack/1.0" "$SERVER_URL/launcher/dist/profilestack-desktop-linux-$ARCH" -o "$DESKTOP_SCRIPT" 2>/dev/null; then
        chmod +x "$DESKTOP_SCRIPT"
        echo "[+] Standalone binary installed to $DESKTOP_SCRIPT"
    else
        echo "[!] Pre-compiled binary for $ARCH not found on server, installing native Python client instead..."
        INSTALL_MODE="script"
    fi
fi

if [ "$INSTALL_MODE" == "script" ]; then
    if ! command -v python3 &>/dev/null; then
        echo "[!] Error: Python 3 is required. Please install python3 first."
        exit 1
    fi
    echo "[*] Downloading ProfileStack Desktop client for Linux..."
    curl -fsSL -A "Mozilla/5.0 ProfileStack/1.0" "$SERVER_URL/launcher/profilestack-desktop.py" -o "$DESKTOP_SCRIPT"
    chmod +x "$DESKTOP_SCRIPT"
fi

echo "[*] Downloading high-resolution SVG icon..."
curl -fsSL -A "Mozilla/5.0 ProfileStack/1.0" "$SERVER_URL/static/img/logo.svg" -o "$ICON_DIR/profilestack.svg" || true

# Register Desktop Entry (.desktop) for ProfileStack Client
DESKTOP_FILE="$APP_DIR/profilestack-desktop.desktop"
echo "[*] Creating Linux desktop menu entry for ProfileStack Desktop..."
cat <<EOF > "$DESKTOP_FILE"
[Desktop Entry]
Name=ProfileStack Desktop
Comment=ProfileStack Anti-Detect Browser Client - Native Profiles
Exec=$DESKTOP_SCRIPT %u
Icon=profilestack
Terminal=false
Type=Application
Categories=Network;WebBrowser;Development;
StartupWMClass=ProfileStackDesktop
MimeType=x-scheme-handler/profilestack;
EOF
chmod +x "$DESKTOP_FILE"

# Setup Dedicated ProfileStack Browser Runner
BROWSER_SCRIPT="$BIN_DIR/profilestack-browser"
BROWSER_DESKTOP_FILE="$APP_DIR/profilestack-browser.desktop"
echo "[*] Configuring dedicated ProfileStack Browser engine runner..."

# Find underlying chromium binary
CHROME_BIN=""
for b in chromium ungoogled-chromium chromium-browser brave-bin brave google-chrome-stable google-chrome; do
    if command -v "$b" &>/dev/null; then
        p="$(command -v "$b")"
        if [[ "$p" != *profilestack-browser* ]]; then
            CHROME_BIN="$p"
            break
        fi
    fi
done

cat <<EOF > "$BROWSER_SCRIPT"
#!/usr/bin/env bash
# ProfileStack Browser - Dedicated Anti-Detect Browser Engine Runner
ENGINE="$CHROME_BIN"
if [ -z "\$ENGINE" ] || [ ! -x "\$ENGINE" ]; then
    for b in chromium ungoogled-chromium chromium-browser brave-bin brave google-chrome-stable google-chrome; do
        if command -v "\$b" &>/dev/null; then
            p="\$(command -v "\$b")"
            if [[ "\$p" != *profilestack-browser* ]]; then
                ENGINE="\$p"
                break
            fi
        fi
    done
fi
if [ -z "\$ENGINE" ]; then
    echo "[!] ProfileStack Browser error: No Chromium engine found." >&2
    echo "    Please install Chromium: sudo pacman -S chromium (or sudo apt install chromium-browser)" >&2
    exit 1
fi
export CHROME_DESKTOP="profilestack-browser.desktop"
exec "\$ENGINE" --class=ProfileStackBrowser --app-id=profilestack "\$@"
EOF
chmod +x "$BROWSER_SCRIPT"

cat <<EOF > "$BROWSER_DESKTOP_FILE"
[Desktop Entry]
Name=ProfileStack Browser
Comment=ProfileStack Anti-Detect Browser Engine
Exec=$BROWSER_SCRIPT %u
Icon=profilestack
Terminal=false
Type=Application
Categories=Network;WebBrowser;
StartupWMClass=ProfileStackBrowser
EOF
chmod +x "$BROWSER_DESKTOP_FILE"

# Register protocol and update system desktop databases
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
        echo "[+] Detected native desktop browser engine: $(command -v "$b")"
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
    echo "      On Fedora:         sudo dnf install chromium"
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
echo "[+] SUCCESS: ProfileStack Desktop is installed on Linux!"
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
