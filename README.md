# Picture Clipboard

Picture Clipboard is a cross-platform Python desktop app for image-only clipboard history. It watches the system clipboard, keeps a bounded history of copied images, shows previews, and lets you copy a previous image back to the clipboard.

## Features

- Image-only capture. Text and files are ignored.
- Preview grid with quick restore back to the clipboard.
- Default retention of `5` images, configurable in settings.
- Show the latest `10`, `20`, or `all` stored images.
- Tray-based app with a configurable global hotkey, defaulting to `Ctrl+Shift+V`.
- JSON-backed settings and file-backed PNG storage for low overhead and simple packaging.

## Keyboard Shortcuts & Navigation

- `h`, `j`, `k`, `l` or `Arrow Keys`: Move through saved image thumbnails
- `Space`: Open quick preview for the focused image
- `Enter` / `Return`: Copy selected image(s) back to the clipboard
- `Cmd+C`: Copy selected image(s) back to the clipboard
- `Click`: Toggle selection on an image (click again to deselect)
- `Cmd+A`: Select all images
- `Esc`: Deselect all images
- `?`: Open the Help menu

## Run

```bash
uv sync
uv run python main.py
```

## App Logo

The app now looks for logo files in the repo `assets/` directory.

Expected filenames:

- `assets/pictureclip-logo.png`
- `assets/pictureclip-logo.icns`
- `assets/pictureclip-logo.ico`

Use your provided logo image as the source artwork and export those files before packaging. During development the app will load `assets/pictureclip-logo.png` automatically if it exists.

## Build Binaries

PyInstaller builds must be created on the target operating system. In practice:

- Build the macOS binary on macOS.
- Build the Linux binary on Linux.
- Build the Windows binary on Windows.

Cross-compiling GUI binaries with PyInstaller is not the practical path here.

Install dependencies first:

```bash
uv sync --all-groups
```

### macOS `.app`

Make sure `assets/pictureclip-logo.icns` exists, then run:

```bash
uv run pyinstaller \
  --name PictureClipboard \
  --windowed \
  --noconfirm \
  --icon assets/pictureclip-logo.icns \
  --add-data "assets/pictureclip-logo.png:assets" \
  main.py
```

Output:

- `dist/PictureClipboard.app`

### Linux binary

Make sure `assets/pictureclip-logo.png` exists, then run:

```bash
uv run pyinstaller \
  --name PictureClipboard \
  --windowed \
  --noconfirm \
  --icon assets/pictureclip-logo.png \
  --add-data "assets/pictureclip-logo.png:assets" \
  main.py
```

Output:

- `dist/PictureClipboard/` for one-folder output

### Windows `.exe`

Make sure `assets/pictureclip-logo.ico` exists, then run:

```powershell
uv run pyinstaller `
  --name PictureClipboard `
  --windowed `
  --noconfirm `
  --icon assets/pictureclip-logo.ico `
  --add-data "assets/pictureclip-logo.png;assets" `
  main.py
```

Output:

- `dist/PictureClipboard/`

If you want a single-file Windows executable instead, add `--onefile`, but startup will be slower.

## Release Notes

After building, test these on the target OS:

- tray icon visibility
- global hotkey registration
- clipboard image detection
- app window show/hide behavior
- restoring an image back to the clipboard

## Notes

- The app stores images under the platform app-data directory used by Qt.
- Global hotkeys may require extra permissions on macOS and can be limited by some Linux Wayland environments.
- You can now select and copy multiple images simultaneously. The paths to multiple images are copied via `text/uri-list`, allowing bulk pasting into Finder, file explorers, and messaging applications.
