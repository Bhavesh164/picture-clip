from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from typing import Any


def default_global_hotkey() -> str:
    return "<cmd>+<shift>+v"


def normalize_global_hotkey(hotkey: str) -> str:
    cleaned = hotkey.strip().lower().replace(" ", "")
    if not cleaned:
        return default_global_hotkey()

    aliases = {
        "<cmd>+<shift>+v",
        "<super>+<shift>+v",
        "<win>+<shift>+v",
        "command+shift+v",
        "cmd+shift+v",
        "windows+shift+v",
        "win+shift+v",
        "super+shift+v",
    }
    if cleaned in aliases:
        return "<cmd>+<shift>+v"

    legacy_default_aliases = {
        "<ctrl>+<shift>+v",
        "ctrl+shift+v",
    }
    if cleaned in legacy_default_aliases:
        return default_global_hotkey()

    return cleaned


def display_global_hotkey(hotkey: str) -> str:
    modifier_name = "Command"
    if sys.platform == "win32":
        modifier_name = "Windows"
    elif sys.platform.startswith("linux"):
        modifier_name = "Super"

    return (
        normalize_global_hotkey(hotkey)
        .replace("<cmd>", modifier_name)
        .replace("<super>", modifier_name)
        .replace("<win>", "Windows")
        .replace("<ctrl>", "Ctrl")
        .replace("<shift>", "Shift")
        .replace("<alt>", "Alt")
        .replace("<option>", "Option")
    )


def parse_global_hotkey(human_text: str) -> str:
    return normalize_global_hotkey(human_text)


@dataclass(slots=True)
class HistoryItem:
    id: str
    created_at: str
    content_hash: str
    image_path: str
    preview_path: str
    width: int
    height: int
    byte_size: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HistoryItem":
        return cls(
            id=str(value["id"]),
            created_at=str(value["created_at"]),
            content_hash=str(value["content_hash"]),
            image_path=str(value["image_path"]),
            preview_path=str(value["preview_path"]),
            width=int(value["width"]),
            height=int(value["height"]),
            byte_size=int(value["byte_size"]),
        )


@dataclass(slots=True)
class AppSettings:
    max_images: int = 5
    poll_interval_ms: int = 700
    global_hotkey: str = default_global_hotkey()
    start_hidden: bool = True

    def normalized(self) -> "AppSettings":
        return AppSettings(
            max_images=max(1, min(self.max_images, 500)),
            poll_interval_ms=max(250, min(self.poll_interval_ms, 5000)),
            global_hotkey=normalize_global_hotkey(self.global_hotkey),
            start_hidden=bool(self.start_hidden),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AppSettings":
        return cls(
            max_images=int(value.get("max_images", 5)),
            poll_interval_ms=int(value.get("poll_interval_ms", 700)),
            global_hotkey=str(value.get("global_hotkey", default_global_hotkey())),
            start_hidden=bool(value.get("start_hidden", True)),
        ).normalized()
