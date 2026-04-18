from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt
from PySide6.QtGui import QImage

from .models import AppSettings, HistoryItem


class AppStore:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.images_dir = self.root_dir / "images"
        self.previews_dir = self.root_dir / "previews"
        self.metadata_path = self.root_dir / "history.json"
        self.settings_path = self.root_dir / "settings.json"
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self) -> AppSettings:
        if not self.settings_path.exists():
            settings = AppSettings().normalized()
            self.save_settings(settings)
            return settings

        data = json.loads(self.settings_path.read_text(encoding="utf-8"))
        return AppSettings.from_dict(data)

    def save_settings(self, settings: AppSettings) -> None:
        self.settings_path.write_text(
            json.dumps(settings.to_dict(), indent=2),
            encoding="utf-8",
        )

    def load_history(self) -> list[HistoryItem]:
        if not self.metadata_path.exists():
            return []

        items: list[HistoryItem] = []
        raw = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        for value in raw:
            item = HistoryItem.from_dict(value)
            if Path(item.image_path).exists() and Path(item.preview_path).exists():
                items.append(item)
        return items

    def save_history(self, items: list[HistoryItem]) -> None:
        payload = [item.to_dict() for item in items]
        self.metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def create_item(self, image: QImage) -> tuple[HistoryItem, bytes]:
        png_bytes = self._to_png_bytes(image)
        content_hash = hashlib.sha256(png_bytes).hexdigest()
        image_path = self.images_dir / f"{content_hash}.png"
        preview_path = self.previews_dir / f"{content_hash}.png"

        item = HistoryItem(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            content_hash=content_hash,
            image_path=str(image_path),
            preview_path=str(preview_path),
            width=image.width(),
            height=image.height(),
            byte_size=len(png_bytes),
        )
        return item, png_bytes

    def persist_item(self, item: HistoryItem, image: QImage, png_bytes: bytes) -> None:
        image_path = Path(item.image_path)
        preview_path = Path(item.preview_path)
        if not image_path.exists():
            image_path.write_bytes(png_bytes)

        if not preview_path.exists():
            preview = image.scaled(
                QSize(220, 220),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            preview.save(str(preview_path), "PNG")

    def prune(self, items: list[HistoryItem], max_images: int) -> list[HistoryItem]:
        if len(items) <= max_images:
            return items

        keep = items[:max_images]
        keep_hashes = {item.content_hash for item in keep}
        for item in items[max_images:]:
            if item.content_hash in keep_hashes:
                continue
            self._unlink_if_exists(Path(item.image_path))
            self._unlink_if_exists(Path(item.preview_path))
        return keep

    @staticmethod
    def _to_png_bytes(image: QImage) -> bytes:
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QIODevice.WriteOnly)
        image.save(buffer, "PNG")
        buffer.close()
        return bytes(data)

    @staticmethod
    def _unlink_if_exists(path: Path) -> None:
        if path.exists():
            path.unlink()
