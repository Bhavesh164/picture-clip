#!/usr/bin/env bash
# build.sh — Build PictureClipboard standalone executables for the current platform.
# Usage: ./build.sh
#
# On macOS  → produces dist/PictureClipboard.app and dist/PictureClipboard.dmg
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
.venv/bin/pyinstaller PictureClipboard.spec --clean --noconfirm

if [[ "$(uname -s)" == "Darwin" ]]; then
    APP_PATH="dist/PictureClipboard.app"
    DMG_PATH="dist/PictureClipboard.dmg"

    if [[ ! -d "$APP_PATH" ]]; then
        echo "Expected app bundle at $APP_PATH but it was not created." >&2
        exit 1
    fi

    echo "==> Creating macOS disk image..."
    staging_dir="$(mktemp -d)"
    cp -R "$APP_PATH" "$staging_dir/"
    
    # Remove quarantine attribute before packaging to avoid gatekeeper issues
    xattr -cr "$staging_dir/PictureClipboard.app"
    
    # Ad-hoc sign the app to fix Accessibility permission issues for global hooks
    codesign --force --deep --sign - "$staging_dir/PictureClipboard.app"

    ln -s /Applications "$staging_dir/Applications"
    hdiutil create \
        -volname "Picture Clipboard" \
        -srcfolder "$staging_dir" \
        -ov \
        -format UDZO \
        "$DMG_PATH" >/dev/null
    rm -rf "$staging_dir"
    rm -rf dist/PictureClipboard
    rm -f dist/.DS_Store
fi

echo ""
echo "==> Build complete!"
echo "    Output: dist/"
ls -la dist/
echo ""

case "$(uname -s)" in
    Darwin)
        echo "    macOS app bundle: dist/PictureClipboard.app"
        echo "    Disk image:       dist/PictureClipboard.dmg"
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
