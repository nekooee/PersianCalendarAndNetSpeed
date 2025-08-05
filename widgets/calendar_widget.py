import jdatetime
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer


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
        self.label.setStyleSheet("background-color: transparent; color: white;")

        layout.addWidget(self.label)

        self.update_time()

        # Set a timer to update the date once a minute
        self.date_update_timer = QTimer(self)
        self.date_update_timer.timeout.connect(self.update_time)
        self.date_update_timer.start(60000)

    def update_time(self):
        """Updates the date label with the current Persian date."""
        # Weekday names are defined locally for a cleaner class scope
        days_in_persian = {
            "Saturday": "شنبه", "Sunday": "یک‌شنبه", "Monday": "دوشنبه",
            "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه", "Thursday": "پنج‌شنبه",
            "Friday": "جمعه"
        }
        now = jdatetime.datetime.now()
        date_str = now.strftime("%Y/%m/%d")
        # Using .get prevents an error if the day name isn't found
        day_str = days_in_persian.get(now.strftime("%A"), "")
        self.label.setText(f"{day_str}\n{date_str}")