"""Two-line world-clock panel for the taskbar widget."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from widgets.timezone_catalog import short_label_for_zone

DEFAULT_TIMEZONE = "Asia/Tehran"
DEFAULT_USE_12H = True


def format_clock_time(dt: datetime, *, use_12h: bool) -> str:
    """Formats hour:minute without seconds; 12h uses AM/PM."""
    if use_12h:
        suffix = "AM" if dt.hour < 12 else "PM"
        hour12 = dt.hour % 12 or 12
        return f"{hour12}:{dt.minute:02d} {suffix}"
    return f"{dt.hour:02d}:{dt.minute:02d}"


class TimezoneWidget(QWidget):
    """Shows remote time on line 1 and the selected zone short name on line 2."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._zone_id = DEFAULT_TIMEZONE
        self._use_12h = DEFAULT_USE_12H
        self._zoneinfo: ZoneInfo | None = None
        self._last_text = ""
        self._minute_timer = QTimer(self)
        self._minute_timer.setSingleShot(True)
        self._minute_timer.timeout.connect(self._on_minute_tick)
        self.init_ui()
        self.set_timezone(self._zone_id)
        # Hidden by default at install; MainWidget may re-enable from config.
        self.setVisible(False)

    def init_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_text_color("#FFFFFF")
        layout.addWidget(self.label)

    @property
    def zone_id(self) -> str:
        return self._zone_id

    @property
    def use_12h(self) -> bool:
        return self._use_12h

    def set_timezone(self, zone_id: str) -> bool:
        """Applies an IANA timezone. Returns False if the id is invalid."""
        zone_id = (zone_id or "").strip() or DEFAULT_TIMEZONE
        try:
            zi = ZoneInfo(zone_id)
        except (ZoneInfoNotFoundError, KeyError, ValueError):
            return False
        self._zone_id = zone_id
        self._zoneinfo = zi
        self.refresh_now()
        return True

    def set_use_12h(self, use_12h: bool):
        """Switches between 12-hour (AM/PM) and 24-hour display."""
        use_12h = bool(use_12h)
        if use_12h == self._use_12h:
            return
        self._use_12h = use_12h
        self.refresh_now()

    def refresh_now(self):
        """Repaints the label from the cached ZoneInfo (no I/O)."""
        if self._zoneinfo is None:
            self.label.setText("—\n—")
            self._last_text = self.label.text()
            return

        now = datetime.now(self._zoneinfo)
        text = f"{format_clock_time(now, use_12h=self._use_12h)}\n{short_label_for_zone(self._zone_id)}"
        # Skip QLabel updates when nothing changed (avoids layout churn every minute).
        if text != self._last_text:
            self.label.setText(text)
            self._last_text = text

    def set_text_color(self, color: str):
        self.label.setStyleSheet(
            f"background-color: transparent; color: {color};"
        )

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_now()
        self._arm_minute_timer()

    def hideEvent(self, event):
        self.stop_timers()
        super().hideEvent(event)

    def stop_timers(self):
        """Stops the minute-aligned refresh timer (used on app quit)."""
        self._minute_timer.stop()

    def _on_minute_tick(self):
        self.refresh_now()
        if self.isVisible():
            self._arm_minute_timer()

    def _arm_minute_timer(self):
        """Fire once at the next minute boundary instead of polling every second."""
        self._minute_timer.stop()
        now = datetime.now()
        # +50ms past the minute avoids landing on a stale second=0 edge case.
        delay_ms = max(50, (60 - now.second) * 1000 - now.microsecond // 1000 + 50)
        self._minute_timer.start(delay_ms)
