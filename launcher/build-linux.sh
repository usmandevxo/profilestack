#!/usr/bin/env bash
# ProfileStack Desktop - Standalone Linux Binary Builder
# Works on CachyOS, Arch Linux, Ubuntu, Debian, Fedora
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="$SCRIPT_DIR/dist"
ARCH="$(uname -m)"

echo "=========================================================="
echo "    Building ProfileStack Desktop Standalone for Linux    "
echo "    Target Architecture: $ARCH                            "
echo "=========================================================="
echo ""

cd "$ROOT_DIR"

# Ensure Python 3 is present
if ! command -v python3 &>/dev/null; then
    echo "[!] Error: python3 is required to build ProfileStack Desktop."
    exit 1
fi

# Ensure pyinstaller is available
BUILD_VENV="/tmp/profilestack-build-venv"
if command -v pyinstaller &>/dev/null; then
    PYINSTALLER_BIN="$(command -v pyinstaller)"
elif [ -f "$ROOT_DIR/.venv/bin/pyinstaller" ]; then
    PYINSTALLER_BIN="$ROOT_DIR/.venv/bin/pyinstaller"
else
    echo "[*] Setting up lightweight builder environment..."
    python3 -m venv "$BUILD_VENV"
    "$BUILD_VENV/bin/pip" install --quiet --upgrade pip pyinstaller
    PYINSTALLER_BIN="$BUILD_VENV/bin/pyinstaller"
fi

mkdir -p "$DIST_DIR"

OUTPUT_NAME="profilestack-desktop-linux-$ARCH"

echo "[*] Compiling standalone single-file ELF executable..."
"$PYINSTALLER_BIN" \
    --onefile \
    --clean \
    --name "$OUTPUT_NAME" \
    --distpath "$DIST_DIR" \
    --workpath "/tmp/pybuild-$ARCH" \
    --specpath "/tmp/pyspec-$ARCH" \
    "$SCRIPT_DIR/profilestack-desktop.py"

chmod +x "$DIST_DIR/$OUTPUT_NAME"
cp "$DIST_DIR/$OUTPUT_NAME" "$DIST_DIR/profilestack-desktop"

echo ""
echo "=========================================================="
echo "[+] BUILD SUCCESSFUL!"
echo "=========================================================="
echo "Executable Path: $DIST_DIR/$OUTPUT_NAME"
echo "Symlink/Alias:   $DIST_DIR/profilestack-desktop"
echo "File Size:       $(du -h "$DIST_DIR/$OUTPUT_NAME" | cut -f1)"
echo ""
echo "To test run the Linux standalone binary:"
echo "  $DIST_DIR/profilestack-desktop --help"
echo "=========================================================="
