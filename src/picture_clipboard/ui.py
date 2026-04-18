from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPixmap,
    QPolygon,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from .models import AppSettings, HistoryItem, display_global_hotkey, parse_global_hotkey


class MainWindow(QMainWindow):
    copy_requested = Signal(list)
    settings_requested = Signal(AppSettings)
    open_folder_requested = Signal()
    visibility_toggled = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Picture Clipboard")
        self.resize(1120, 760)
        self._history: list[HistoryItem] = []
        self._visible_limit: int | None = 10
        self._preview_dialog: QuickPreviewDialog | None = None

        central = QWidget(self)
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        logo_label = QLabel()
        logo_label.setPixmap(create_app_icon().pixmap(36, 36))
        logo_label.setFixedSize(40, 40)
        logo_label.setAlignment(Qt.AlignCenter)

        title = QLabel("Clipboard Image History")
        title.setObjectName("title")
        subtitle = QLabel(
            "Image-only clipboard history with preview, quick restore, and bounded retention."
        )
        subtitle.setObjectName("subtitle")

        title_wrap = QVBoxLayout()
        title_row.addWidget(logo_label)
        title_row.addWidget(title)
        title_row.addStretch(1)
        title_wrap.addLayout(title_row)
        title_wrap.addWidget(subtitle)
        root.addLayout(title_wrap)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.show_10_button = QPushButton("10")
        self.show_20_button = QPushButton("20")
        self.show_all_button = QPushButton("All")
        self.copy_button = QPushButton("Copy")
        self.copy_button.setEnabled(False)
        self.help_button = QPushButton("Help")
        self.settings_button = QPushButton("Save Settings")
        self.open_folder_button = QPushButton("Open Storage Folder")
        self.status_label = QLabel("Waiting for clipboard images")
        self.status_label.setObjectName("status")

        toolbar.addWidget(self.show_10_button)
        toolbar.addWidget(self.show_20_button)
        toolbar.addWidget(self.show_all_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.copy_button)
        toolbar.addWidget(self.help_button)
        root.addLayout(toolbar)

        body = QGridLayout()
        body.setHorizontalSpacing(12)
        body.setVerticalSpacing(12)
        body.setColumnStretch(0, 7)
        body.setColumnStretch(1, 2)
        root.addLayout(body, stretch=1)

        self.history_list = QListWidget()
        self.history_list.setViewMode(QListWidget.IconMode)
        self.history_list.setResizeMode(QListWidget.Adjust)
        self.history_list.setMovement(QListWidget.Static)
        self.history_list.setIconSize(QSize(180, 124))
        self.history_list.setGridSize(QSize(196, 158))
        self.history_list.setSpacing(8)
        self.history_list.setWordWrap(False)
        self.history_list.setUniformItemSizes(True)
        self.history_list.setWrapping(True)
        self.history_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.history_list.setDragEnabled(False)
        self.history_list.itemSelectionChanged.connect(self._sync_selection_state)
        self.history_list.itemDoubleClicked.connect(lambda _: self._emit_copy_request())
        body.addWidget(self.history_list, 0, 0)

        settings_panel = QGroupBox("Settings")
        settings_panel.setMinimumWidth(250)
        settings_panel.setMaximumWidth(268)
        panel_layout = QVBoxLayout(settings_panel)
        panel_layout.setContentsMargins(12, 14, 12, 12)
        panel_layout.setSpacing(8)

        self.max_images_spin = QSpinBox()
        self.max_images_spin.setRange(1, 500)
        self.max_images_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.max_images_spin.setMinimumWidth(0)
        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(250, 5000)
        self.poll_interval_spin.setSingleStep(50)
        self.poll_interval_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.poll_interval_spin.setMinimumWidth(0)
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setMinimumWidth(0)
        self.start_hidden_checkbox = QCheckBox("Start minimized to tray")
        self.start_hidden_checkbox.setToolTip("When checked, the app launches silently to the system tray without showing this window.")

        panel_layout.addLayout(self._stacked_setting("Stored images", self.max_images_spin))
        panel_layout.addLayout(self._stacked_setting("Poll interval (ms)", self.poll_interval_spin))
        panel_layout.addLayout(self._stacked_setting("Global hotkey", self.hotkey_input))
        panel_layout.addWidget(self.start_hidden_checkbox)
        panel_layout.addWidget(self.settings_button)
        panel_layout.addWidget(self.open_folder_button)
        panel_layout.addStretch(1)
        body.addWidget(settings_panel, 0, 1, alignment=Qt.AlignTop)

        footer = QHBoxLayout()
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        root.addLayout(footer)

        self.show_10_button.clicked.connect(lambda: self.set_visible_limit(10))
        self.show_20_button.clicked.connect(lambda: self.set_visible_limit(20))
        self.show_all_button.clicked.connect(lambda: self.set_visible_limit(None))
        self.copy_button.clicked.connect(self._emit_copy_request)
        self.help_button.clicked.connect(self.show_help_dialog)
        self.settings_button.clicked.connect(self._emit_settings_request)
        self.open_folder_button.clicked.connect(self.open_folder_requested.emit)

        self.help_shortcut = QShortcut(QKeySequence("?"), self)
        self.help_shortcut.activated.connect(self.show_help_dialog)

        self.select_all_shortcut = QShortcut(QKeySequence.SelectAll, self)
        self.select_all_shortcut.activated.connect(self.history_list.selectAll)

        self.deselect_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.deselect_shortcut.activated.connect(self.history_list.clearSelection)

        self._init_tray()
        self._apply_styles()
        # Intercept Space on the list widget for quick preview
        self.history_list.installEventFilter(self)
        self.history_list.setFocus()

    def set_history(self, history: list[HistoryItem]) -> None:
        self._history = history
        self._render_history()

    def prepend_item(self, item: HistoryItem) -> None:
        self._history.insert(0, item)
        self._render_history()

    def set_settings(self, settings: AppSettings) -> None:
        self.max_images_spin.setValue(settings.max_images)
        self.poll_interval_spin.setValue(settings.poll_interval_ms)
        self.hotkey_input.setText(display_global_hotkey(settings.global_hotkey))
        self.start_hidden_checkbox.setChecked(settings.start_hidden)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_visible_limit(self, limit: int | None) -> None:
        self._visible_limit = limit
        self._render_history()

    def show_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide()
            return
        self.show_window()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.tray_icon.isVisible():
            self.hide()
            self.set_status("App hidden to tray")
            event.ignore()
            return
        super().closeEvent(event)

    def notify_hotkey_issue(self, message: str) -> None:
        self.tray_icon.showMessage(
            "Picture Clipboard",
            message,
            QSystemTrayIcon.Warning,
            5000,
        )

    def show_help_dialog(self) -> None:
        launch_hotkey = display_global_hotkey(self.hotkey_input.text().strip())
        dialog = HelpDialog(self, launch_hotkey)
        dialog.exec()

    def _emit_copy_request(self) -> None:
        items = self.history_list.selectedItems()
        if not items:
            return
        image_paths = [str(item.data(Qt.UserRole)) for item in items]
        self.copy_requested.emit(image_paths)

    def _emit_settings_request(self) -> None:
        settings = AppSettings(
            max_images=self.max_images_spin.value(),
            poll_interval_ms=self.poll_interval_spin.value(),
            global_hotkey=parse_global_hotkey(self.hotkey_input.text()),
            start_hidden=self.start_hidden_checkbox.isChecked(),
        ).normalized()
        self.settings_requested.emit(settings)

    def _sync_selection_state(self) -> None:
        self.copy_button.setEnabled(len(self.history_list.selectedItems()) > 0)

    def _render_history(self) -> None:
        selected_path = None
        current_item = self.history_list.currentItem()
        if current_item is not None:
            selected_path = current_item.data(Qt.UserRole)

        self.history_list.clear()
        visible_items = self._history if self._visible_limit is None else self._history[: self._visible_limit]
        restored_selection = False
        for item in visible_items:
            pixmap = QPixmap(item.preview_path)
            list_item = QListWidgetItem(QIcon(pixmap), f"{item.width} x {item.height}")
            list_item.setData(Qt.UserRole, item.image_path)
            list_item.setData(Qt.UserRole + 1, item.created_at)
            list_item.setData(Qt.UserRole + 2, f"{item.width} x {item.height}")
            list_item.setToolTip(item.created_at)
            list_item.setSizeHint(QSize(188, 150))
            list_item.setTextAlignment(Qt.AlignCenter)
            thumb_font = QFont()
            thumb_font.setPointSize(11)
            list_item.setFont(thumb_font)
            self.history_list.addItem(list_item)
            if selected_path is not None and item.image_path == selected_path:
                self.history_list.setCurrentItem(list_item)
                restored_selection = True

        if not visible_items:
            placeholder = QListWidgetItem("No clipboard images captured yet")
            placeholder.setFlags(Qt.NoItemFlags)
            self.history_list.addItem(placeholder)
        elif not restored_selection and self.history_list.count() > 0:
            self.history_list.setCurrentRow(0)
            self.history_list.selectAll()
        self._sync_selection_state()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.history_list and event.type() == QEvent.KeyPress:
            key = event.key()
            if key == Qt.Key_Space and not event.isAutoRepeat():
                item = self.history_list.currentItem()
                if item is None and self.history_list.selectedItems():
                    item = self.history_list.selectedItems()[0]
                if item is not None:
                    self._show_preview_for_item(item)
                    return True  # consumed
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in {Qt.Key_Return, Qt.Key_Enter} and self.history_list.selectedItems():
            self._emit_copy_request()
            event.accept()
            return
        if event.text() in {"h", "j", "k", "l"}:
            self._move_with_vim_key(event.text())
            event.accept()
            return
        super().keyPressEvent(event)

    def _move_with_vim_key(self, key: str) -> None:
        current_index = self.history_list.currentIndex()
        if not current_index.isValid():
            return
        movement = {
            "h": QAbstractItemView.MoveLeft,
            "j": QAbstractItemView.MoveDown,
            "k": QAbstractItemView.MoveUp,
            "l": QAbstractItemView.MoveRight,
        }[key]
        next_index = self.history_list.moveCursor(movement, Qt.NoModifier)
        if next_index.isValid():
            self.history_list.setCurrentIndex(next_index)
            self.history_list.scrollTo(next_index)

    def _show_preview_for_item(self, item: QListWidgetItem) -> None:
        image_path = item.data(Qt.UserRole)
        if image_path is None:
            return
        if self._preview_dialog is None:
            self._preview_dialog = QuickPreviewDialog(self)
        self._preview_dialog.set_image(
            str(image_path),
            item.data(Qt.UserRole + 2) or "",
            item.data(Qt.UserRole + 1) or "",
        )
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    def _stacked_setting(self, label_text: str, field: QWidget) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setProperty("settingLabel", True)
        layout.addWidget(label)
        layout.addWidget(field)
        return layout

    def _init_tray(self) -> None:
        icon = create_app_icon()
        self.tray_icon = QSystemTrayIcon(icon, self)
        self.setWindowIcon(icon)
        self.tray_icon.setToolTip("Picture Clipboard")
        tray_menu = QMenu(self)
        show_action = QAction("Show / Hide", self)
        show_action.triggered.connect(self.toggle_visibility)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._handle_tray_activation)
        self.tray_icon.show()

    def _handle_tray_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.Trigger,
            QSystemTrayIcon.DoubleClick,
            QSystemTrayIcon.MiddleClick,
        }:
            self.toggle_visibility()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: #0c1016;
                color: #e8eef7;
                font-family: "Avenir Next", "Segoe UI", sans-serif;
                font-size: 14px;
            }
            QMainWindow {
                background: #0c1016;
            }
            QLabel#title {
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #8d9bb0;
            }
            QLabel#status {
                color: #7c8da8;
                padding: 4px 0;
            }
            QLabel[settingLabel="true"] {
                color: #c7d3e5;
                font-size: 12px;
                font-weight: 600;
                padding-left: 2px;
            }
            QPushButton {
                background: #171e28;
                color: #f4f8ff;
                border: 1px solid #2b3648;
                border-radius: 8px;
                padding: 6px 12px;
                min-height: 28px;
                font-size: 13px;
            }
            QPushButton:hover {
                background: #202a37;
                border-color: #3c4c66;
            }
            QPushButton:disabled {
                background: #121821;
                color: #62718a;
                border-color: #1f2937;
            }
            QListWidget {
                background: #111722;
                border: 1px solid #232d3d;
                border-radius: 18px;
                padding: 10px;
                outline: none;
            }
            QListWidget::item {
                background: #141b26;
                border: 1px solid #212c3b;
                border-radius: 14px;
                margin: 3px;
                padding: 6px 6px 10px 6px;
            }
            QListWidget::item:selected {
                background: #1d2736;
                border: 1px solid #65a4ff;
            }
            QGroupBox {
                background: #111722;
                border: 1px solid #232d3d;
                border-radius: 18px;
                margin-top: 10px;
                padding: 10px;
                font-weight: 600;
            }
            QGroupBox::title {
                color: #dfe8f4;
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px;
            }
            QLineEdit, QSpinBox {
                background: #0b1118;
                color: #edf3fb;
                border: 1px solid #324258;
                border-radius: 8px;
                padding: 6px 8px;
                min-height: 18px;
                font-size: 13px;
            }
            QLineEdit:focus, QSpinBox:focus {
                border-color: #65a4ff;
            }
            QCheckBox {
                spacing: 8px;
                color: #d8e2f2;
            }
            """
        )


class HelpDialog(QDialog):
    def __init__(self, parent: QWidget, launch_hotkey: str) -> None:
        super().__init__(parent)
        self.setWindowTitle("Picture Clipboard Help")
        self.resize(560, 480)
        self.setStyleSheet(parent.styleSheet())
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        
        title = QLabel("Keyboard Shortcuts")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f4f8ff;")
        layout.addWidget(title)
        
        shortcuts = [
            ("?", "Open this help window"),
            (launch_hotkey, "Show or hide the app globally"),
            ("h j k l or Arrow Keys", "Move through saved thumbnails"),
            ("Space", "Open quick preview for the focused image"),
            ("Enter / Return", "Copy selected image(s) back to the clipboard"),
            ("Click", "Toggle selection on an image"),
            ("Cmd+A", "Select all images"),
            ("Esc", "Deselect all images"),
            ("10 / 20 / All", "Change how many thumbnails are visible"),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(12)
        grid.setColumnStretch(1, 1)
        for row, (key, desc) in enumerate(shortcuts):
            key_lbl = QLabel(key)
            key_lbl.setStyleSheet("font-weight: bold; color: #65a4ff;")
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet("color: #d8e2f2;")
            grid.addWidget(key_lbl, row, 0)
            grid.addWidget(desc_lbl, row, 1)
            
        layout.addLayout(grid)
        
        notes_title = QLabel("Notes")
        notes_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f4f8ff; margin-top: 12px;")
        layout.addWidget(notes_title)
        
        notes = QLabel(
            "• The global shortcut can be changed in the Settings panel.<br>"
            "• When copying multiple images, they will be pasted into applications as multiple dropped files."
        )
        notes.setWordWrap(True)
        notes.setStyleSheet("color: #7c8da8;")
        layout.addWidget(notes)
        layout.addStretch(1)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(80)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)


class QuickPreviewDialog(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Quick Preview")
        self.resize(940, 720)
        self._source_pixmap = QPixmap()

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(640, 420)
        self.image_label.setStyleSheet(
            "background:#0b1118; border:1px solid #232d3d; border-radius:16px;"
        )

        meta = QHBoxLayout()
        self.dimensions_label = QLabel()
        self.timestamp_label = QLabel()
        self.timestamp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta.addWidget(self.dimensions_label)
        meta.addStretch(1)
        meta.addWidget(self.timestamp_label)

        hint = QLabel("Esc closes preview")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#8092ad;")

        root.addWidget(self.image_label, stretch=1)
        root.addLayout(meta)
        root.addWidget(hint)

        self.setStyleSheet(
            """
            QWidget {
                background: #0c1016;
                color: #ecf3fd;
                font-family: "Avenir Next", "Segoe UI", sans-serif;
            }
            """
        )

    def set_image(self, image_path: str, dimensions: str, timestamp: str) -> None:
        self._source_pixmap = QPixmap(image_path)
        if self._source_pixmap.isNull():
            self.image_label.setText("Preview unavailable")
            self.image_label.setPixmap(QPixmap())
            return
        self.dimensions_label.setText(dimensions)
        self.timestamp_label.setText(timestamp)
        self._render_pixmap()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._render_pixmap()

    def _render_pixmap(self) -> None:
        if self._source_pixmap.isNull():
            return
        scaled = self._source_pixmap.scaled(
            self.image_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)


def create_app_icon() -> QIcon:
    asset_icon = load_packaged_icon()
    if asset_icon is not None:
        return asset_icon

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QColor("#2b3440"))
    painter.drawRoundedRect(4, 4, 56, 56, 16, 16)
    painter.setBrush(QColor("#d7bd7b"))
    painter.drawRoundedRect(14, 15, 36, 34, 10, 10)
    painter.setBrush(QColor("#0e141d"))
    painter.drawRoundedRect(18, 19, 28, 25, 7, 7)
    painter.setBrush(QColor("#d7bd7b"))
    painter.drawRoundedRect(24, 11, 16, 11, 6, 6)
    painter.setBrush(QColor("#0e141d"))
    painter.drawEllipse(29, 13, 6, 6)
    painter.setBrush(QColor("#44576d"))
    painter.drawEllipse(20, 22, 24, 24)
    painter.setBrush(QColor("#0e141d"))
    painter.drawPolygon(
        QPolygon(
            [
                QPoint(32, 21),
                QPoint(36, 30),
                QPoint(30, 30),
            ]
        )
    )
    painter.drawPolygon(QPolygon([QPoint(29, 30), QPoint(22, 30), QPoint(26, 22)]))
    painter.drawPolygon(QPolygon([QPoint(36, 31), QPoint(41, 24), QPoint(42, 31)]))
    painter.drawPolygon(QPolygon([QPoint(31, 34), QPoint(37, 34), QPoint(35, 40)]))
    painter.end()
    return QIcon(pixmap)


def load_packaged_icon() -> QIcon | None:
    for candidate in icon_candidates():
        if not candidate.exists():
            continue
        pixmap = QPixmap(str(candidate))
        if pixmap.isNull():
            icon = QIcon(str(candidate))
            if icon.isNull():
                continue
            probe = icon.pixmap(64, 64)
            if probe.isNull():
                continue
            return icon
        return build_square_icon(pixmap)
    return None


def icon_candidates() -> list[Path]:
    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
        executable = Path(sys.executable).resolve().parent
        roots.extend([executable, executable / "_internal"])

    project_root = Path(__file__).resolve().parents[2]
    roots.append(project_root)

    candidates: list[Path] = []
    names = [
        "assets/picture-clip.png",
        "assets/pictureclip-logo.svg",
        "assets/pictureclip-logo.png",
        "assets/pictureclip-logo.ico",
        "assets/pictureclip-logo.icns",
    ]
    for root in roots:
        for name in names:
            candidates.append(root / name)
    return candidates


def build_square_icon(source: QPixmap) -> QIcon:
    if source.isNull():
        return QIcon()

    side = min(source.width(), source.height())
    x_offset = max(0, (source.width() - side) // 2)
    y_offset = max(0, (source.height() - side) // 2)
    square = source.copy(x_offset, y_offset, side, side)

    canvas = QPixmap(side, side)
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    
    path = QPainterPath()
    path.addRoundedRect(0, 0, side, side, side * 0.22, side * 0.22)
    painter.setClipPath(path)

    scaled = square.scaled(
        side, side,
        Qt.IgnoreAspectRatio,
        Qt.SmoothTransformation,
    )
    painter.drawPixmap(0, 0, scaled)
    painter.end()

    return QIcon(canvas)
