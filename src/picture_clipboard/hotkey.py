from __future__ import annotations

from PySide6.QtCore import QMetaObject, QObject, Qt, Signal, Slot

try:
    from pynput import keyboard
except Exception:  # pragma: no cover - optional runtime failure
    keyboard = None


class GlobalHotkeyManager(QObject):
    activated = Signal()
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener = None
        self._hotkey = ""

    def start(self, hotkey: str) -> None:
        self.stop()
        self._hotkey = hotkey
        if keyboard is None:
            self.error.emit("Global hotkey support is unavailable because pynput could not be loaded.")
            return

        try:
            self._listener = keyboard.GlobalHotKeys({hotkey: self._on_hotkey_pressed})
            self._listener.start()
        except Exception as exc:  # pragma: no cover - depends on OS hooks
            self._listener = None
            self.error.emit(f"Global hotkey could not be started: {exc}")

    def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _on_hotkey_pressed(self) -> None:
        """Called from pynput's background thread — marshal to the Qt main thread."""
        QMetaObject.invokeMethod(self, "_emit_activated", Qt.QueuedConnection)

    @Slot()
    def _emit_activated(self) -> None:
        self.activated.emit()
