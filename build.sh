#!/usr/bin/env bash
# build.sh — Build PictureClipboard standalone executables for the current platform.
# Usage: ./build.sh
#
# On macOS  → produces dist/PictureClipboard.app  (+ dist/PictureClipboard/)
# On Linux  → produces dist/PictureClipboard/
# On Windows (via Git Bash / WSL) → produces dist/PictureClipboard/
#
# Cross-platform builds (Linux & Windows from macOS) are not natively possible
# with PyInstaller. Run this script on each target OS, or use CI (GitHub Actions).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Cleaning previous build artifacts..."
rm -rf build/ dist/

echo "==> Building PictureClipboard with PyInstaller..."
.venv/bin/pyinstaller PictureClipboard.spec --noconfirm

echo ""
echo "==> Build complete!"
echo "    Output: dist/"
ls -la dist/
echo ""

case "$(uname -s)" in
    Darwin)
        echo "    macOS app bundle: dist/PictureClipboard.app"
        echo "    Directory build:  dist/PictureClipboard/"
        ;;
    Linux)
        echo "    Directory build:  dist/PictureClipboard/"
        echo "    Run with:         ./dist/PictureClipboard/PictureClipboard"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        echo "    Directory build:  dist\\PictureClipboard\\"
        echo "    Run with:         dist\\PictureClipboard\\PictureClipboard.exe"
        ;;
esac
