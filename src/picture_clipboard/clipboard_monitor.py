from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QClipboard, QImage


class ClipboardMonitor(QObject):
    image_captured = Signal(QImage)

    def __init__(
        self,
        clipboard: QClipboard,
        poll_interval_ms: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._clipboard = clipboard
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._last_fingerprint: tuple[int, int, int] | None = None
        self.set_interval(poll_interval_ms)

    def start(self) -> None:
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def set_interval(self, interval_ms: int) -> None:
        self._timer.setInterval(interval_ms)

    def on_image_captured(self, callback: Callable[[QImage], None]) -> None:
        self.image_captured.connect(callback)

    def _poll(self) -> None:
        mime_data = self._clipboard.mimeData()
        if mime_data is None or not mime_data.hasImage():
            self._last_fingerprint = None
            return

        image = self._clipboard.image()
        if image.isNull():
            return

        fingerprint = (
            image.cacheKey(),
            image.width(),
            image.height(),
        )
        if fingerprint == self._last_fingerprint:
            return

        self._last_fingerprint = fingerprint
        self.image_captured.emit(image)
