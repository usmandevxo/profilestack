#!/usr/bin/env bash
# ProfileStack Desktop Installer for Linux (CachyOS, Arch, Ubuntu, Debian, Fedora)
set -e

SERVER_URL="https://profilestack.rerouter.online"
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

# Find underlying chromium binary (Google Chrome prioritized)
CHROME_BIN=""
if [ -n "$PROFILESTACK_BROWSER_BIN" ] && [ -x "$PROFILESTACK_BROWSER_BIN" ]; then
    CHROME_BIN="$PROFILESTACK_BROWSER_BIN"
elif [ -n "$CHROME_BIN" ] && [ -x "$CHROME_BIN" ]; then
    : # already set
else
    for p in "/usr/bin/google-chrome-stable" "/usr/bin/google-chrome" "/opt/google/chrome/google-chrome" "/opt/google/chrome/chrome" "/usr/bin/chromium" "/usr/bin/chromium-browser"; do
        if [ -x "$p" ]; then
            CHROME_BIN="$p"
            break
        fi
    done
    if [ -z "$CHROME_BIN" ]; then
        for b in google-chrome-stable google-chrome chromium ungoogled-chromium chromium-browser brave-browser brave-bin brave; do
            if command -v "$b" &>/dev/null; then
                p="$(command -v "$b")"
                if [[ "$p" != *profilestack* ]]; then
                    CHROME_BIN="$p"
                    break
                fi
            fi
        done
    fi
fi

cat <<EOF > "$BROWSER_SCRIPT"
#!/usr/bin/env bash
# ProfileStack Browser - Dedicated Anti-Detect Browser Engine Runner
set -e

# 1. If invoked with --desktop or --gui, launch ProfileStack Desktop Manager
for arg in "\$@"; do
    if [ "\$arg" = "--desktop" ] || [ "\$arg" = "--gui" ] || [ "\$arg" = "--manager" ]; then
        if command -v profilestack-desktop &>/dev/null; then
            exec profilestack-desktop
        elif [ -x "\$HOME/.local/bin/profilestack-desktop" ]; then
            exec "\$HOME/.local/bin/profilestack-desktop"
        fi
    fi
done

# 2. Prefer running through profilestack-desktop --browser (handles full anti-detect spoofing, extensions, and configs)
if [ -x "\$HOME/.local/bin/profilestack-desktop" ]; then
    exec "\$HOME/.local/bin/profilestack-desktop" --browser "\$@"
elif command -v profilestack-desktop &>/dev/null; then
    exec "\$(command -v profilestack-desktop)" --browser "\$@"
elif [ -f "\$HOME/ProfileStack/launcher/profilestack-desktop.py" ] && command -v python3 &>/dev/null; then
    exec python3 "\$HOME/ProfileStack/launcher/profilestack-desktop.py" --browser "\$@"
elif [ -f "/www/wwwroot/profilestack/launcher/profilestack-desktop.py" ] && command -v python3 &>/dev/null; then
    exec python3 "/www/wwwroot/profilestack/launcher/profilestack-desktop.py" --browser "\$@"
fi

# 3. Fallback: locate engine and run strictly with isolated profile (NEVER personal Chrome profile)
ENGINE="$CHROME_BIN"
if [ -z "\$ENGINE" ] || [ ! -x "\$ENGINE" ]; then
    for p in "/usr/bin/google-chrome-stable" "/usr/bin/google-chrome" "/opt/google/chrome/google-chrome" "/opt/google/chrome/chrome" "/usr/bin/chromium" "/usr/bin/chromium-browser"; do
        if [ -x "\$p" ]; then
            ENGINE="\$p"
            break
        fi
    done
    if [ -z "\$ENGINE" ]; then
        for b in google-chrome-stable google-chrome chromium ungoogled-chromium chromium-browser brave-browser brave-bin brave; do
            if command -v "\$b" &>/dev/null; then
                p="\$(command -v "\$b")"
                if [[ "\$p" != *profilestack* ]]; then
                    ENGINE="\$p"
                    break
                fi
            fi
        done
    fi
fi

if [ -z "\$ENGINE" ]; then
    echo "[!] ProfileStack Browser error: No Chromium engine found." >&2
    echo "    Please install Google Chrome or Chromium: sudo pacman -S google-chrome (or chromium)" >&2
    exit 1
fi

PROFILE="Default"
URLS=()
while [[ \$# -gt 0 ]]; do
    case "\$1" in
        -p|--profile)
            PROFILE="\$2"
            shift 2
            ;;
        --profile=*)
            PROFILE="\${1#*=}"
            shift
            ;;
        -l|--list)
            echo "======================================================="
            echo "         Local ProfileStack Profiles"
            echo "======================================================="
            if [ -d "\$HOME/ProfileStack/profiles" ]; then
                for d in "\$HOME/ProfileStack/profiles"/*; do
                    if [ -d "\$d" ]; then
                        echo "  * \$(basename "\$d")"
                    fi
                done
            fi
            echo "======================================================="
            exit 0
            ;;
        -h|--help)
            echo "ProfileStack Browser - Isolated Anti-Detect Browser Engine"
            echo ""
            echo "Usage:"
            echo "  profilestack-browser [options] [URL]"
            echo "  profilestack-browser -p <profile_name> [URL]"
            echo ""
            echo "Options:"
            echo "  -p, --profile <name>   Launch a specific ProfileStack profile (default: 'Default')"
            echo "  -l, --list             List all local ProfileStack profiles"
            echo "  --desktop, --gui       Launch the ProfileStack Desktop manager interface"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            URLS+=("\$1")
            shift
            ;;
    esac
done

PROFILE_DIR="\$HOME/ProfileStack/profiles/\$PROFILE"
mkdir -p "\$PROFILE_DIR"
export CHROME_DESKTOP="profilestack-browser.desktop"

ARGS=(
    --user-data-dir="\$PROFILE_DIR"
    --class=ProfileStackBrowser
    --log-level=3
    --silent-debugger-extension-api
    --password-store=basic
    --use-mock-keychain
    --no-first-run
    --no-default-browser-check
    --disable-sync
    --disable-signin-scoped-device-id
    --disable-features=AccountConsistency,DesktopIdentityConsistency,LockProfileCookieDatabase
    --disable-blink-features=AutomationControlled
    --disable-session-crashed-bubble
    --restore-last-session
    --ozone-platform-hint=auto
)

if [ \${#URLS[@]} -eq 0 ]; then
    exec "\$ENGINE" "\${ARGS[@]}" "https://www.google.com"
else
    exec "\$ENGINE" "\${ARGS[@]}" "\${URLS[@]}"
fi
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
