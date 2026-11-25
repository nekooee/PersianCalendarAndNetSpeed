"""Searchable timezone picker dialog (keeps the context menu uncluttered)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from widgets.timezone_catalog import TimezoneEntry, filter_timezone_catalog, find_timezone_entry
from widgets.timezone_widget import format_clock_time


class TimezonePickerDialog(QDialog):
    """Filterable city list; returns the selected IANA zone via selected_zone_id."""

    def __init__(
        self,
        parent=None,
        *,
        current_zone_id: str = "Asia/Tehran",
        use_12h: bool = True,
        app_icon=None,
    ):
        super().__init__(parent)
        self.selected_zone_id = current_zone_id
        self._use_12h = use_12h
        self._current_zone_id = current_zone_id
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(120)
        self._filter_timer.timeout.connect(self._apply_filter)
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(30_000)
        self._clock_timer.timeout.connect(self._refresh_visible_times)

        self.setWindowTitle("انتخاب منطقه زمانی")
        if app_icon is not None:
            self.setWindowIcon(app_icon)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.setMinimumSize(460, 520)
        self.resize(480, 560)

        self._build_ui()
        self._apply_filter()
        self._clock_timer.start()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        hint = QLabel("نام شهر یا کشور را بنویسید تا لیست فیلتر شود.")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("مثال: تهران، London، Turkey، Asia/Dubai")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_query_changed)
        root.addWidget(self.search_edit)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #666;")
        root.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.itemDoubleClicked.connect(self._accept_current)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        root.addWidget(self.list_widget, stretch=1)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_font = QFont(self.font())
        preview_font.setPointSize(max(11, preview_font.pointSize() + 1))
        self.preview_label.setFont(preview_font)
        root.addWidget(self.preview_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_btn = QPushButton("انصراف")
        cancel_btn.clicked.connect(self.reject)
        ok_btn = QPushButton("انتخاب")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._accept_current)
        buttons.addWidget(cancel_btn)
        buttons.addWidget(ok_btn)
        root.addLayout(buttons)

        self.search_edit.setFocus()

    def _on_query_changed(self, _text: str):
        self._filter_timer.start()

    def _apply_filter(self):
        query = self.search_edit.text()
        matches = filter_timezone_catalog(query)
        previous = self._selected_zone_from_list() or self._current_zone_id

        self.list_widget.setUpdatesEnabled(False)
        self.list_widget.clear()
        select_row = 0
        for index, entry in enumerate(matches):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry.zone_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, entry)
            item.setText(self._row_text(entry))
            self.list_widget.addItem(item)
            if entry.zone_id == previous:
                select_row = index
        self.list_widget.setUpdatesEnabled(True)

        total = len(matches)
        self.count_label.setText(f"{total} مورد" if total else "موردی پیدا نشد")
        if total:
            self.list_widget.setCurrentRow(select_row)
            self.list_widget.scrollToItem(self.list_widget.currentItem())
        else:
            self.preview_label.setText("—")

    def _row_text(self, entry: TimezoneEntry) -> str:
        time_str = self._time_for_zone(entry.zone_id)
        # LTR time on the left-ish side of an RTL row stays readable with a tab-like gap.
        return f"{entry.list_label}    {entry.city_en}    {time_str}"

    def _time_for_zone(self, zone_id: str) -> str:
        try:
            now = datetime.now(ZoneInfo(zone_id))
        except Exception:
            return "--:--"
        return format_clock_time(now, use_12h=self._use_12h)

    def _refresh_visible_times(self):
        """Updates only the times already shown (cheap; dialog stays open rarely)."""
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            entry = item.data(Qt.ItemDataRole.UserRole + 1)
            if isinstance(entry, TimezoneEntry):
                item.setText(self._row_text(entry))
        self._update_preview()

    def _selected_zone_from_list(self) -> str | None:
        item = self.list_widget.currentItem()
        if not item:
            return None
        zone_id = item.data(Qt.ItemDataRole.UserRole)
        return zone_id if isinstance(zone_id, str) else None

    def _on_current_changed(self, current: QListWidgetItem | None, _previous):
        self._update_preview(current)

    def _update_preview(self, item: QListWidgetItem | None = None):
        item = item or self.list_widget.currentItem()
        if not item:
            self.preview_label.setText("—")
            return
        zone_id = item.data(Qt.ItemDataRole.UserRole)
        entry = find_timezone_entry(zone_id) if isinstance(zone_id, str) else None
        label = entry.short_label if entry else str(zone_id)
        time_str = self._time_for_zone(zone_id) if isinstance(zone_id, str) else "--:--"
        self.preview_label.setText(f"{time_str}  ·  {label}")

    def _accept_current(self):
        zone_id = self._selected_zone_from_list()
        if not zone_id:
            return
        self.selected_zone_id = zone_id
        self.accept()

    def closeEvent(self, event):
        self._clock_timer.stop()
        self._filter_timer.stop()
        super().closeEvent(event)
