#!/usr/bin/env bash
# uninstall-linux.sh - Completely removes Picture Clipboard and all its settings/data.
# This script is designed for Linux systems.

echo "Uninstalling Picture Clipboard (Linux)..."

# 1. Force quit the app if running
echo "Stopping any running instances..."
pkill -f "PictureClipboard" || true
pkill -f "Picture Clipboard" || true

# Give it a moment to terminate
sleep 1

# 2. Remove standard Linux Qt/PySide meta data paths
DATA_PATHS=(
    "$HOME/.local/share/Picture Clipboard"
    "$HOME/.local/share/PictureClipboard"
    "$HOME/.config/Picture Clipboard"
    "$HOME/.config/PictureClipboard"
    "$HOME/.cache/Picture Clipboard"
    "$HOME/.cache/PictureClipboard"
)

for target in "${DATA_PATHS[@]}"; do
    if [ -e "$target" ]; then
        echo "Removing data at: $target"
        rm -rf "$target"
    fi
done

# 3. Optional: Remove binaries or desktop shortcuts if installed locally
INSTALL_PATHS=(
    "/opt/PictureClipboard"
    "/usr/local/bin/PictureClipboard"
    "$HOME/.local/bin/PictureClipboard"
    "$HOME/.local/share/applications/PictureClipboard.desktop"
    "/usr/share/applications/PictureClipboard.desktop"
)

for target in "${INSTALL_PATHS[@]}"; do
    if [ -e "$target" ] || [ -L "$target" ]; then
        echo "Attempting to remove installation file at: $target"
        # We try to remove generally, might require sudo for /opt or /usr so we suppress errors if it fails.
        rm -rf "$target" 2>/dev/null || sudo rm -rf "$target" 2>/dev/null || echo "Could not remove $target (requires root?)"
    fi
done

echo "Done! Picture Clipboard has been completely uninstalled from Linux."
