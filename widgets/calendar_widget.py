import jdatetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

DAYS_IN_PERSIAN = {
    "Saturday": "شنبه", "Sunday": "یک‌شنبه", "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه", "Thursday": "پنج‌شنبه",
    "Friday": "جمعه"
}


def format_jalali_date(*, multiline: bool = True) -> str:
    """Returns the current Jalali date string for display or tray tooltip."""
    now = jdatetime.datetime.now()
    date_str = now.strftime("%Y/%m/%d")
    day_str = DAYS_IN_PERSIAN.get(now.strftime("%A"), "")
    if multiline:
        return f"{day_str}\n{date_str}"
    if day_str:
        return f"{day_str} {date_str}"
    return date_str


def jalali_day_of_month() -> int:
    """Current day-of-month in the Jalali calendar (1-31)."""
    return jdatetime.datetime.now().day


class CalendarWidget(QWidget):
    """A widget for displaying the Persian (Jalali) calendar date."""

    def __init__(self, parent=None):
        """Initializes the widget."""
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """Initializes the widget's UI."""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_text_color("#FFFFFF")

        layout.addWidget(self.label)

        self.update_time()

        # Set a timer to update the date once a minute
        self.date_update_timer = QTimer(self)
        self.date_update_timer.timeout.connect(self.update_time)
        self.date_update_timer.start(60000)

    def update_time(self):
        """Updates the date label with the current Persian date."""
        self.label.setText(format_jalali_date(multiline=True))
        parent = self.parent()
        if parent is not None and hasattr(parent, "_update_tray"):
            parent._update_tray()
        elif parent is not None and hasattr(parent, "_update_tray_tooltip"):
            parent._update_tray_tooltip()

    def get_date_tooltip(self) -> str:
        """Single-line Jalali date suitable for tray tooltips."""
        return format_jalali_date(multiline=False)

    def set_text_color(self, color: str):
        """Applies the given text color to the date label."""
        self.label.setStyleSheet(
            f"background-color: transparent; color: {color};"
        )
