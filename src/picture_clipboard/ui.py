from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QColor,
    QFont,
    QIcon,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygon,
    QShortcut,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
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
    annotation_saved = Signal(QImage)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Picture Clipboard")
        self.resize(1120, 760)
        self._history: list[HistoryItem] = []
        self._visible_limit = 5
        self._max_images = 5
        self._preview_dialog: QuickPreviewDialog | None = None
        self._default_thumbnail_columns = 4
        self._minimum_thumbnail_cell_width = 180
        self._thumbnail_layout_slack = 32
        self._window_presented = False

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
        self.show_5_button = QPushButton("5")
        self.show_10_button = QPushButton("10")
        self.copy_button = QPushButton("Copy")
        self.copy_button.setEnabled(False)
        self.help_button = QPushButton("Help")
        self.settings_button = QPushButton("Save Settings")
        self.open_folder_button = QPushButton("Open Storage Folder")
        self.status_label = QLabel("Waiting for clipboard images")
        self.status_label.setObjectName("status")

        toolbar.addWidget(self.show_5_button)
        toolbar.addWidget(self.show_10_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.copy_button)
        toolbar.addWidget(self.help_button)
        root.addLayout(toolbar)

        body = QGridLayout()
        body.setHorizontalSpacing(12)
        body.setVerticalSpacing(12)
        body.setColumnStretch(0, 1)
        body.setColumnStretch(1, 0)
        root.addLayout(body, stretch=1)

        self.history_list = QListWidget()
        self.history_list.setViewMode(QListWidget.IconMode)
        self.history_list.setResizeMode(QListWidget.Adjust)
        self.history_list.setMovement(QListWidget.Static)
        self.history_list.setIconSize(QSize(180, 124))
        self.history_list.setGridSize(QSize(196, 158))
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

        self.poll_interval_spin = QSpinBox()
        self.poll_interval_spin.setRange(250, 5000)
        self.poll_interval_spin.setSingleStep(50)
        self.poll_interval_spin.setButtonSymbols(QSpinBox.NoButtons)
        self.poll_interval_spin.setMinimumWidth(0)
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setMinimumWidth(0)
        self.start_hidden_checkbox = QCheckBox("Start minimized to tray")
        self.start_hidden_checkbox.setToolTip("When checked, the app launches silently to the system tray without showing this window.")

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

        self.show_5_button.clicked.connect(lambda: self.set_history_size(5))
        self.show_10_button.clicked.connect(lambda: self.set_history_size(10))
        self.copy_button.clicked.connect(self._emit_copy_request)
        self.help_button.clicked.connect(self.show_help_dialog)
        self.settings_button.clicked.connect(self._emit_settings_request)
        self.open_folder_button.clicked.connect(self.open_folder_requested.emit)

        self.help_shortcut = QShortcut(QKeySequence("?"), self)
        self.help_shortcut.activated.connect(self.show_help_dialog)

        self.select_all_shortcut = QShortcut(QKeySequence.SelectAll, self)
        self.select_all_shortcut.activated.connect(self._toggle_select_all)

        self.deselect_shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        self.deselect_shortcut.activated.connect(self.history_list.clearSelection)

        self.copy_shortcut = QShortcut(QKeySequence.Copy, self)
        self.copy_shortcut.activated.connect(self._emit_copy_request)

        self.copy_c_shortcut = QShortcut(QKeySequence(Qt.Key_C), self)
        self.copy_c_shortcut.activated.connect(self._emit_copy_request)

        self._init_tray()
        self._apply_styles()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)
        self.history_list.setFocus()
        self._update_history_layout_metrics()

    def set_history(self, history: list[HistoryItem]) -> None:
        self._history = history
        self._render_history()

    def prepend_item(self, item: HistoryItem) -> None:
        self._history.insert(0, item)
        self._render_history()

    def set_settings(self, settings: AppSettings) -> None:
        self._max_images = settings.max_images
        self._visible_limit = settings.max_images
        self._sync_history_size_buttons()
        self.poll_interval_spin.setValue(settings.poll_interval_ms)
        self.hotkey_input.setText(display_global_hotkey(settings.global_hotkey))
        self.start_hidden_checkbox.setChecked(settings.start_hidden)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_history_size(self, max_images: int) -> None:
        self._max_images = 5 if max_images <= 5 else 10
        self._visible_limit = self._max_images
        self._sync_history_size_buttons()
        self._render_history()
        self._emit_settings_request()

    def show_window(self) -> None:
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        app = QApplication.instance()
        if app is not None:
            app.setActiveWindow(self)
        self._window_presented = True
        self._focus_history_list()

    def hide_window(self) -> None:
        self._window_presented = False
        self.hide()

    def toggle_visibility(self) -> None:
        if self.isVisible() and not self.isMinimized():
            self.hide_window()
        else:
            self.show_window()

    def is_presented(self) -> bool:
        return self._window_presented

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self.tray_icon.isVisible():
            self.hide_window()
            self.set_status("App hidden to tray")
            event.ignore()
            return
        super().closeEvent(event)

    def showEvent(self, event) -> None:  # noqa: N802
        self._window_presented = not self.isMinimized()
        super().showEvent(event)

    def hideEvent(self, event) -> None:  # noqa: N802
        self._window_presented = False
        super().hideEvent(event)

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
            max_images=self._max_images,
            poll_interval_ms=self.poll_interval_spin.value(),
            global_hotkey=parse_global_hotkey(self.hotkey_input.text()),
            start_hidden=self.start_hidden_checkbox.isChecked(),
        ).normalized()
        self.settings_requested.emit(settings)

    def _sync_history_size_buttons(self) -> None:
        self.show_5_button.setProperty("selected", self._max_images == 5)
        self.show_10_button.setProperty("selected", self._max_images == 10)
        self.show_5_button.style().unpolish(self.show_5_button)
        self.show_5_button.style().polish(self.show_5_button)
        self.show_10_button.style().unpolish(self.show_10_button)
        self.show_10_button.style().polish(self.show_10_button)

    def _sync_selection_state(self) -> None:
        self.copy_button.setEnabled(len(self.history_list.selectedItems()) > 0)

    def _toggle_select_all(self) -> None:
        count = self.history_list.count()
        if count == 0:
            return
            
        all_selected = True
        for i in range(count):
            item = self.history_list.item(i)
            if item.flags() != Qt.NoItemFlags and not item.isSelected():
                all_selected = False
                break
                
        if all_selected:
            self.history_list.clearSelection()
        else:
            self.history_list.selectAll()

    def _render_history(self) -> None:
        selected_paths: set[str] = set()
        for sel in self.history_list.selectedItems():
            p = sel.data(Qt.UserRole)
            if p is not None:
                selected_paths.add(str(p))

        self.history_list.clear()
        visible_items = self._history[: self._visible_limit]
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

        if not visible_items:
            placeholder = QListWidgetItem("No clipboard images captured yet")
            placeholder.setFlags(Qt.NoItemFlags)
            self.history_list.addItem(placeholder)
        elif selected_paths:
            restored_any = False
            for i in range(self.history_list.count()):
                w = self.history_list.item(i)
                if str(w.data(Qt.UserRole)) in selected_paths:
                    w.setSelected(True)
                    if not restored_any:
                        self.history_list.setCurrentItem(w)
                    restored_any = True
            if not restored_any and self.history_list.count() > 0:
                self._select_item(self.history_list.item(0))
        else:
            # First load defaults to the most recent image.
            if self.history_list.count() > 0:
                self._select_item(self.history_list.item(0))
        self._update_history_layout_metrics()
        self._sync_selection_state()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched in {self.history_list, self.history_list.viewport()} and event.type() in {
            QEvent.Resize,
            QEvent.Show,
            QEvent.LayoutRequest,
        }:
            self._update_history_layout_metrics()
        if watched in {self.history_list, self.history_list.viewport()} and event.type() == QEvent.KeyPress:
            key = event.key()
            # Space → quick preview
            if key == Qt.Key_Space and not event.isAutoRepeat():
                item = self.history_list.currentItem()
                if item is None and self.history_list.selectedItems():
                    item = self.history_list.selectedItems()[0]
                if item is not None:
                    self._show_preview_for_item(item)
                    return True

        if event.type() in {QEvent.ShortcutOverride, QEvent.KeyPress} and self._should_handle_navigation_event(watched, event):
            if event.type() == QEvent.ShortcutOverride:
                event.accept()
                return True
            self._navigate(self._navigation_direction(event.key()))
            return True
        return super().eventFilter(watched, event)

    def _should_handle_navigation_event(self, watched, event) -> bool:
        if QApplication.activeWindow() is not self:
            return False
        focus_widget = QApplication.focusWidget()
        if focus_widget is None or not self._belongs_to_main_window(focus_widget):
            return False
        if self._navigation_keys_blocked(focus_widget):
            return False
        return self._navigation_direction(event.key()) is not None

    def _navigation_direction(self, key: int) -> str | None:
        nav_map = {
            Qt.Key_H: "left",
            Qt.Key_Left: "left",
            Qt.Key_L: "right",
            Qt.Key_Right: "right",
            Qt.Key_J: "down",
            Qt.Key_Down: "down",
            Qt.Key_K: "up",
            Qt.Key_Up: "up",
        }
        return nav_map.get(key)

    def _navigation_keys_blocked(self, focus_widget: QWidget) -> bool:
        return isinstance(focus_widget, (QLineEdit, QAbstractSpinBox))

    def _belongs_to_main_window(self, widget: QWidget) -> bool:
        return widget is self or self.isAncestorOf(widget)

    def _focus_history_list(self) -> None:
        if self.history_list.count() == 0:
            return
        if self.history_list.currentItem() is None:
            self.history_list.setCurrentRow(0)
        self.history_list.setFocus(Qt.OtherFocusReason)

    def _select_item(self, item: QListWidgetItem) -> None:
        from PySide6.QtCore import QItemSelectionModel

        self.history_list.setCurrentItem(item, QItemSelectionModel.ClearAndSelect)

    def _navigate(self, direction: str) -> None:
        count = self.history_list.count()
        if count == 0:
            return
        current_row = self.history_list.currentRow()
        if current_row < 0:
            current_row = 0

        # Calculate how many items fit per row by inspecting the grid
        grid_w = self.history_list.gridSize().width()
        viewport_w = self.history_list.viewport().width()
        cols = max(1, viewport_w // grid_w) if grid_w > 0 else 1

        if direction == "left":
            new_row = max(0, current_row - 1)
        elif direction == "right":
            new_row = min(count - 1, current_row + 1)
        elif direction == "down":
            new_row = min(count - 1, current_row + cols)
        elif direction == "up":
            new_row = max(0, current_row - cols)
        else:
            return

        target_item = self.history_list.item(new_row)
        if target_item is not None:
            self._select_item(target_item)
            self.history_list.scrollToItem(target_item)

    def _update_history_layout_metrics(self) -> None:
        viewport_width = self.history_list.viewport().width()
        if viewport_width <= 0:
            return

        columns = self._resolved_thumbnail_columns(viewport_width)
        available_width = max(150, viewport_width - self._thumbnail_layout_slack)
        cell_width = max(150, available_width // columns)
        item_width = max(138, cell_width - 8)
        icon_width = max(122, item_width - 16)
        icon_height = max(84, round(icon_width * 124 / 180))
        cell_height = icon_height + 34
        item_height = cell_height - 8

        self.history_list.setGridSize(QSize(cell_width, cell_height))
        self.history_list.setIconSize(QSize(icon_width, icon_height))

        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            if item.flags() == Qt.NoItemFlags:
                continue
            item.setSizeHint(QSize(item_width, item_height))

    def _resolved_thumbnail_columns(self, viewport_width: int) -> int:
        if viewport_width >= self._default_thumbnail_columns * self._minimum_thumbnail_cell_width:
            return self._default_thumbnail_columns
        return max(1, viewport_width // self._minimum_thumbnail_cell_width)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_history_layout_metrics()


    def _show_preview_for_item(self, item: QListWidgetItem) -> None:
        image_path = item.data(Qt.UserRole)
        if image_path is None:
            return
        if self._preview_dialog is None:
            self._preview_dialog = QuickPreviewDialog(self)
            self._preview_dialog.save_requested.connect(self.annotation_saved.emit)
        self._preview_dialog.set_image(
            str(image_path),
            item.data(Qt.UserRole + 2) or "",
            item.data(Qt.UserRole + 1) or "",
        )
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    def _navigate_preview(self, direction: str) -> None:
        if self.history_list.count() == 0:
            return
        current_item = self.history_list.currentItem()
        if current_item is None and self.history_list.selectedItems():
            current_item = self.history_list.selectedItems()[0]
        
        if current_item is None:
            current_row = 0
        else:
            current_row = self.history_list.row(current_item)

        grid_w = self.history_list.gridSize().width()
        viewport_w = self.history_list.viewport().width()
        cols = max(1, viewport_w // grid_w) if grid_w > 0 else 1

        if direction == "left":
            new_row = max(0, current_row - 1)
        elif direction == "right":
            new_row = min(self.history_list.count() - 1, current_row + 1)
        elif direction == "down":
            new_row = min(self.history_list.count() - 1, current_row + cols)
        elif direction == "up":
            new_row = max(0, current_row - cols)
        else:
            return
            
        target_item = self.history_list.item(new_row)
        if target_item is not None and target_item.flags() != Qt.NoItemFlags:
            self._select_item(target_item)
            self.history_list.scrollToItem(target_item)
            self._show_preview_for_item(target_item)

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
            QPushButton[selected="true"] {
                background: #21344f;
                border-color: #65a4ff;
                color: #ffffff;
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
            ("e in preview", "Toggle annotation tools"),
            ("g in edit preview", "Choose highlight"),
            ("s in preview", "Save annotated copy"),
            ("z in edit preview", "Undo last annotation"),
            ("c in edit preview", "Clear annotations"),
            ("c", "Copy selected image(s) to the clipboard"),
            ("Click", "Toggle selection on an image"),
            ("Cmd+A / Ctrl+A", "Select / Deselect all images"),
            ("Esc", "Deselect all images"),
            ("5 / 10", "Choose how many clipboard images are stored"),
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


class AnnotationStroke:
    def __init__(
        self,
        points: list[QPointF],
        color: QColor,
        width: float,
        erase: bool = False,
        shape: str = "path",
    ) -> None:
        self.points = points
        self.color = color
        self.width = width
        self.erase = erase
        self.shape = shape


class AnnotationCanvas(QWidget):
    changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 420)
        self.setMouseTracking(True)
        self.setStyleSheet("background:#0b1118; border:1px solid #232d3d; border-radius:16px;")
        self._image = QImage()
        self._strokes: list[AnnotationStroke] = []
        self._active_stroke: AnnotationStroke | None = None
        self._editing = False
        self._tool = "highlight"
        self._target_rect = QRectF()

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._strokes.clear()
        self._active_stroke = None
        self.changed.emit(False)
        self.update()

    def set_editing(self, editing: bool) -> None:
        self._editing = editing
        self.setCursor(Qt.CrossCursor if editing else Qt.ArrowCursor)

    def set_tool(self, tool: str) -> None:
        self._tool = tool

    def clear_annotations(self) -> None:
        if not self._strokes and self._active_stroke is None:
            return
        self._strokes.clear()
        self._active_stroke = None
        self.changed.emit(False)
        self.update()

    def undo_annotation(self) -> None:
        if not self._strokes:
            return
        self._strokes.pop()
        self._active_stroke = None
        self.changed.emit(bool(self._strokes))
        self.update()

    def has_annotations(self) -> bool:
        return bool(self._strokes)

    def annotated_image(self) -> QImage:
        if self._image.isNull():
            return QImage()
        result = self._image.convertToFormat(QImage.Format_ARGB32)
        painter = QPainter(result)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_strokes(painter)
        painter.end()
        return result

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#0b1118"))

        if self._image.isNull():
            painter.setPen(QColor("#8092ad"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Preview unavailable")
            painter.end()
            return

        self._target_rect = self._fit_rect()
        painter.drawImage(self._target_rect, self._image)
        scale = self._target_rect.width() / max(1, self._image.width())
        painter.save()
        painter.translate(self._target_rect.topLeft())
        painter.scale(scale, scale)
        self._paint_strokes(painter)
        if self._active_stroke is not None:
            self._paint_stroke(painter, self._active_stroke)
        painter.restore()
        painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._target_rect = self._fit_rect()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if not self._editing or event.button() != Qt.LeftButton or self._image.isNull():
            super().mousePressEvent(event)
            return
        point = self._image_point(event.position())
        if point is None:
            return
        color, screen_width, erase, shape = self._tool_style()
        scale = self._target_rect.width() / max(1, self._image.width())
        self._active_stroke = AnnotationStroke(
            [point],
            color,
            screen_width / max(scale, 0.01),
            erase,
            shape,
        )
        self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._active_stroke is None:
            super().mouseMoveEvent(event)
            return
        point = self._image_point(event.position())
        if point is None:
            return
        if self._active_stroke.shape == "rect":
            self._active_stroke.points = [self._active_stroke.points[0], point]
        else:
            self._active_stroke.points.append(point)
        self.changed.emit(True)
        self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._active_stroke is None or event.button() != Qt.LeftButton:
            super().mouseReleaseEvent(event)
            return
        if len(self._active_stroke.points) == 1:
            self._active_stroke.points.append(self._active_stroke.points[0])
        if self._active_stroke.erase:
            changed = self._erase_strokes_near(self._active_stroke.points, self._active_stroke.width)
            self.changed.emit(changed or bool(self._strokes))
        else:
            self._strokes.append(self._active_stroke)
            self.changed.emit(True)
        self._active_stroke = None
        self.update()

    def _fit_rect(self) -> QRectF:
        if self._image.isNull():
            return QRectF()
        bounds = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        image_ratio = self._image.width() / max(1, self._image.height())
        bounds_ratio = bounds.width() / max(1.0, bounds.height())
        if image_ratio > bounds_ratio:
            width = bounds.width()
            height = width / image_ratio
        else:
            height = bounds.height()
            width = height * image_ratio
        return QRectF(
            bounds.x() + (bounds.width() - width) / 2,
            bounds.y() + (bounds.height() - height) / 2,
            width,
            height,
        )

    def _image_point(self, widget_point: QPointF) -> QPointF | None:
        if self._target_rect.isNull():
            self._target_rect = self._fit_rect()
        if not self._target_rect.contains(widget_point):
            return None
        x = (widget_point.x() - self._target_rect.x()) * self._image.width() / self._target_rect.width()
        y = (widget_point.y() - self._target_rect.y()) * self._image.height() / self._target_rect.height()
        return QPointF(x, y)

    def _tool_style(self) -> tuple[QColor, float, bool, str]:
        if self._tool == "pen":
            return QColor("#ff5a68"), 3.0, False, "path"
        if self._tool == "erase":
            return QColor(255, 255, 255, 120), 30.0, True, "path"
        return QColor("#ff2f45"), 3.0, False, "rect"

    def _paint_strokes(self, painter: QPainter) -> None:
        for stroke in self._strokes:
            self._paint_stroke(painter, stroke)

    def _paint_stroke(self, painter: QPainter, stroke: AnnotationStroke) -> None:
        if not stroke.points:
            return
        if stroke.shape == "rect":
            self._paint_rect_stroke(painter, stroke)
            return

        path = QPainterPath(stroke.points[0])
        for point in stroke.points[1:]:
            path.lineTo(point)

        painter.save()
        pen = QPen(stroke.color, max(1.0, stroke.width))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        if stroke.erase:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.restore()

    def _paint_rect_stroke(self, painter: QPainter, stroke: AnnotationStroke) -> None:
        if len(stroke.points) < 2:
            return
        rect = QRectF(stroke.points[0], stroke.points[-1]).normalized()
        if rect.width() < 1 or rect.height() < 1:
            return
        painter.save()
        pen = QPen(stroke.color, max(1.0, stroke.width))
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawRect(rect)
        painter.restore()

    def _erase_strokes_near(self, points: list[QPointF], radius: float) -> bool:
        original_count = len(self._strokes)
        self._strokes = [
            stroke
            for stroke in self._strokes
            if not self._stroke_hits_eraser(stroke, points, radius)
        ]
        return len(self._strokes) != original_count

    def _stroke_hits_eraser(
        self,
        stroke: AnnotationStroke,
        eraser_points: list[QPointF],
        radius: float,
    ) -> bool:
        threshold = radius + stroke.width / 2
        threshold_sq = threshold * threshold
        if stroke.shape == "rect" and len(stroke.points) >= 2:
            rect = QRectF(stroke.points[0], stroke.points[-1]).normalized()
            inflated = rect.adjusted(-threshold, -threshold, threshold, threshold)
            return any(inflated.contains(point) for point in eraser_points)
        for stroke_point in stroke.points:
            for eraser_point in eraser_points:
                dx = stroke_point.x() - eraser_point.x()
                dy = stroke_point.y() - eraser_point.y()
                if dx * dx + dy * dy <= threshold_sq:
                    return True
        return False


class QuickPreviewDialog(QWidget):
    save_requested = Signal(QImage)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.setWindowTitle("Quick Preview")
        self.resize(940, 720)
        self._source_image = QImage()
        self._editing = False
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.edit_button = QPushButton("Edit")
        self.highlight_button = QPushButton("Highlight")
        self.pen_button = QPushButton("Pen")
        self.erase_button = QPushButton("Erase")
        self.undo_button = QPushButton("Undo")
        self.clear_button = QPushButton("Clear")
        self.save_button = QPushButton("Save Copy")
        for button in (
            self.edit_button,
            self.highlight_button,
            self.pen_button,
            self.erase_button,
            self.undo_button,
            self.clear_button,
            self.save_button,
        ):
            button.setFocusPolicy(Qt.NoFocus)
            button.setEnabled(False)
        toolbar.addWidget(self.edit_button)
        toolbar.addWidget(self.highlight_button)
        toolbar.addWidget(self.pen_button)
        toolbar.addWidget(self.erase_button)
        toolbar.addWidget(self.undo_button)
        toolbar.addWidget(self.clear_button)
        toolbar.addStretch(1)
        toolbar.addWidget(self.save_button)

        self.canvas = AnnotationCanvas()

        meta = QHBoxLayout()
        self.dimensions_label = QLabel()
        self.timestamp_label = QLabel()
        self.timestamp_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        meta.addWidget(self.dimensions_label)
        meta.addStretch(1)
        meta.addWidget(self.timestamp_label)

        hint = QLabel("Esc closes preview · e edit · g/p/r tools · z undo · c clear · s save")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet("color:#8092ad;")

        root.addLayout(toolbar)
        root.addWidget(self.canvas, stretch=1)
        root.addLayout(meta)
        root.addWidget(hint)
        self.canvas.installEventFilter(self)

        self.edit_button.clicked.connect(self._toggle_editing)
        self.highlight_button.clicked.connect(lambda: self._set_tool("highlight"))
        self.pen_button.clicked.connect(lambda: self._set_tool("pen"))
        self.erase_button.clicked.connect(lambda: self._set_tool("erase"))
        self.undo_button.clicked.connect(self.canvas.undo_annotation)
        self.clear_button.clicked.connect(self.canvas.clear_annotations)
        self.save_button.clicked.connect(self._save_copy)
        self.canvas.changed.connect(self._set_dirty)

        self.setStyleSheet(
            """
            QWidget {
                background: #0c1016;
                color: #ecf3fd;
                font-family: "Avenir Next", "Segoe UI", sans-serif;
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
            QPushButton[active="true"] {
                background: #21344f;
                border-color: #65a4ff;
            }
            QPushButton:disabled {
                background: #121821;
                color: #62718a;
                border-color: #1f2937;
            }
            """
        )
        self._set_tool("highlight")
        self._sync_edit_controls()

    def set_image(self, image_path: str, dimensions: str, timestamp: str) -> None:
        self._source_image = QImage(image_path)
        self.canvas.set_image(self._source_image)
        self._editing = False
        self.canvas.set_editing(False)
        self._dirty = False
        if self._source_image.isNull():
            self.dimensions_label.setText("")
            self.timestamp_label.setText("")
            self._sync_edit_controls()
            return
        self.dimensions_label.setText(dimensions)
        self.timestamp_label.setText(timestamp)
        self._sync_edit_controls()
        self.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self._handle_key_event(event):
            return
        super().keyPressEvent(event)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802
        if watched is self.canvas and event.type() == QEvent.KeyPress:
            return self._handle_key_event(event)
        return super().eventFilter(watched, event)

    def _handle_key_event(self, event) -> bool:
        key = event.key()
        if key == Qt.Key_Escape:
            self.close()
            event.accept()
            return True
        elif key == Qt.Key_E:
            self._toggle_editing()
            event.accept()
            return True
        elif self._editing and key == Qt.Key_G:
            self._set_tool("highlight")
            event.accept()
            return True
        elif self._editing and key == Qt.Key_P:
            self._set_tool("pen")
            event.accept()
            return True
        elif self._editing and key == Qt.Key_R:
            self._set_tool("erase")
            event.accept()
            return True
        elif self._editing and key == Qt.Key_Z:
            self.canvas.undo_annotation()
            event.accept()
            return True
        elif self._editing and key == Qt.Key_C:
            self.canvas.clear_annotations()
            event.accept()
            return True
        elif self._editing and key == Qt.Key_S:
            self._save_copy()
            event.accept()
            return True
        elif key in {Qt.Key_H, Qt.Key_Left, Qt.Key_K, Qt.Key_Up}:
            if hasattr(self.parent(), "_navigate_preview"):
                direction = "left" if key in {Qt.Key_H, Qt.Key_Left} else "up"
                self.parent()._navigate_preview(direction)
            event.accept()
            return True
        elif key in {Qt.Key_L, Qt.Key_Right, Qt.Key_J, Qt.Key_Down}:
            if hasattr(self.parent(), "_navigate_preview"):
                direction = "right" if key in {Qt.Key_L, Qt.Key_Right} else "down"
                self.parent()._navigate_preview(direction)
            event.accept()
            return True
        return False

    def _toggle_editing(self) -> None:
        if self._source_image.isNull():
            return
        self._editing = not self._editing
        self.canvas.set_editing(self._editing)
        self._sync_edit_controls()

    def _set_tool(self, tool: str) -> None:
        self.canvas.set_tool(tool)
        for button, button_tool in (
            (self.highlight_button, "highlight"),
            (self.pen_button, "pen"),
            (self.erase_button, "erase"),
        ):
            button.setProperty("active", button_tool == tool)
            button.style().unpolish(button)
            button.style().polish(button)

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._sync_edit_controls()

    def _sync_edit_controls(self) -> None:
        can_edit = not self._source_image.isNull()
        self.edit_button.setEnabled(can_edit)
        self.edit_button.setProperty("active", self._editing)
        self.edit_button.style().unpolish(self.edit_button)
        self.edit_button.style().polish(self.edit_button)
        for button in (self.highlight_button, self.pen_button, self.erase_button):
            button.setEnabled(can_edit and self._editing)
        self.undo_button.setEnabled(can_edit and self._editing and self.canvas.has_annotations())
        self.clear_button.setEnabled(can_edit and self._editing and self.canvas.has_annotations())
        self.save_button.setEnabled(can_edit and self._dirty and self.canvas.has_annotations())

    def _save_copy(self) -> None:
        if self._source_image.isNull() or not self.canvas.has_annotations():
            return
        image = self.canvas.annotated_image()
        if image.isNull():
            return
        self.save_requested.emit(image)
        self._dirty = False
        self._sync_edit_controls()


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
