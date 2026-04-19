#!/usr/bin/env bash
# uninstall.sh - Completely removes Picture Clipboard and all its settings/data.
# This script is designed for macOS.

echo "Uninstalling Picture Clipboard..."

# 1. Force quit the app if running
echo "Stopping any running instances..."
pkill -f "Picture Clipboard" || true
pkill -f "PictureClipboard" || true

# Give it a moment to terminate
sleep 1

# 2. Remove the actual App bundle
APP_PATHS=(
    "/Applications/PictureClipboard.app"
    "$HOME/Applications/PictureClipboard.app"
)

for app_path in "${APP_PATHS[@]}"; do
    if [ -d "$app_path" ]; then
        echo "Removing App bundle at: $app_path"
        rm -rf "$app_path"
    fi
done

# 3. Remove application support, caches, and preferences data
# The app uses PySide6 with ApplicationName "Picture Clipboard"
DATA_PATHS=(
    "$HOME/Library/Application Support/Picture Clipboard"
    "$HOME/Library/Application Support/PictureClipboard"
    "$HOME/Library/Caches/Picture Clipboard"
    "$HOME/Library/Caches/PictureClipboard"
    "$HOME/Library/Preferences/Picture Clipboard.plist"
    "$HOME/Library/Preferences/PictureClipboard.plist"
)

for target in "${DATA_PATHS[@]}"; do
    if [ -e "$target" ]; then
        echo "Removing data at: $target"
        rm -rf "$target"
    fi
done

echo "Done! Picture Clipboard has been completely uninstalled."
