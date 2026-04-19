from __future__ import annotations

import sys
import time
from pathlib import Path

from PySide6.QtCore import QStandardPaths, QUrl, QMimeData
from PySide6.QtGui import QDesktopServices, QGuiApplication, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QMessageBox

from .clipboard_monitor import ClipboardMonitor
from .hotkey import GlobalHotkeyManager
from .models import AppSettings, HistoryItem
from .store import AppStore
from .ui import MainWindow, create_app_icon


class PictureClipboardApp:
    def __init__(self) -> None:
        self.qt_app = QApplication(sys.argv)
        self.qt_app.setApplicationName("Picture Clipboard")
        self.qt_app.setQuitOnLastWindowClosed(False)
        self.qt_app.setWindowIcon(create_app_icon())

        data_root = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        self.store = AppStore(data_root)
        self.settings = self.store.load_settings()
        self.store.save_settings(self.settings)
        self.history = self.store.prune(self.store.load_history(), self.settings.max_images)
        self.store.save_history(self.history)

        self.window = MainWindow()
        self.window.set_settings(self.settings)
        self.window.set_history(self.history)
        self.window.set_status(f"Loaded {len(self.history)} image(s)")
        self.window.copy_requested.connect(self.copy_image_to_clipboard)
        self.window.settings_requested.connect(self.save_settings)
        self.window.open_folder_requested.connect(self.open_storage_folder)

        self.clipboard = QGuiApplication.clipboard()
        self.monitor = ClipboardMonitor(
            self.clipboard,
            self.settings.poll_interval_ms,
            self.window,
        )
        self.monitor.on_image_captured(self.capture_image)

        self.hotkey_manager = GlobalHotkeyManager(self.window)
        self._last_hotkey_toggle_at = 0.0
        self.hotkey_manager.activated.connect(self.handle_hotkey_activation)
        self.hotkey_manager.error.connect(self.window.notify_hotkey_issue)

    def run(self) -> int:
        self.monitor.start()
        self.hotkey_manager.start(self.settings.global_hotkey)
        self.window.show_window()
        return self.qt_app.exec()

    def capture_image(self, image: QImage) -> None:
        if image.isNull():
            return

        item, png_bytes = self.store.create_item(image)
        for index, existing in enumerate(self.history):
            if existing.content_hash != item.content_hash:
                continue
            self.history.pop(index)
            self.history.insert(0, existing)
            self.store.save_history(self.history)
            self.window.set_history(self.history)
            self.window.set_status("Clipboard image already stored and moved to the top")
            return

        self.store.persist_item(item, image, png_bytes)
        self.history.insert(0, item)
        self.history = self.store.prune(self.history, self.settings.max_images)
        self.store.save_history(self.history)
        self.window.set_history(self.history)
        self.window.set_status(f"Captured image {item.width}x{item.height}")

    def copy_image_to_clipboard(self, image_paths: list[str]) -> None:
        if not image_paths:
            return

        valid_paths = [p for p in image_paths if Path(p).exists()]

        if not valid_paths:
            if len(image_paths) == 1:
                QMessageBox.warning(
                    self.window,
                    "Picture Clipboard",
                    "The selected image could not be loaded.",
                )
            return

        if len(valid_paths) == 1:
            pixmap = QPixmap(valid_paths[0])
            if pixmap.isNull():
                QMessageBox.warning(
                    self.window,
                    "Picture Clipboard",
                    "The selected image could not be loaded.",
                )
                return
            self.clipboard.setPixmap(pixmap)
            self.window.set_status(f"Copied {Path(valid_paths[0]).name} back to clipboard")
        else:
            try:
                mime_data = QMimeData()
                mime_data.setUrls([QUrl.fromLocalFile(p) for p in valid_paths])
                self.clipboard.setMimeData(mime_data)
                self.window.set_status(f"Copied {len(valid_paths)} images to clipboard")
            except Exception:  # noqa: BLE001
                pixmap = QPixmap(valid_paths[-1])
                if not pixmap.isNull():
                    self.clipboard.setPixmap(pixmap)
                self.window.set_status(f"Copied {len(valid_paths)} images (last as pixmap)")

    def save_settings(self, settings: AppSettings) -> None:
        self.settings = settings
        self.store.save_settings(settings)
        self.history = self.store.prune(self.history, settings.max_images)
        self.store.save_history(self.history)
        self.window.set_settings(settings)
        self.window.set_history(self.history)
        self.monitor.set_interval(settings.poll_interval_ms)
        self.hotkey_manager.start(settings.global_hotkey)
        self.window.set_status("Settings saved")

    def open_storage_folder(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.store.root_dir)))

    def handle_hotkey_activation(self) -> None:
        now = time.monotonic()
        if now - self._last_hotkey_toggle_at < 0.3:
            return
        self._last_hotkey_toggle_at = now
        self.window.toggle_visibility()


def main() -> int:
    app = PictureClipboardApp()
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
