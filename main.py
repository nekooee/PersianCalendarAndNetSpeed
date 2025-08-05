import sys
import jdatetime
import os
import signal
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QMenu, QVBoxLayout
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QAction

# Windows-specific imports for direct window control
try:
    import win32gui
    import win32con

    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

# --- Constants ---
DAYS_IN_PERSIAN = {
    "Saturday": "شنبه", "Sunday": "یک‌شنبه", "Monday": "دوشنبه",
    "Tuesday": "سه‌شنبه", "Wednesday": "چهارشنبه", "Thursday": "پنج‌شنبه",
    "Friday": "جمعه"
}
WINDOW_POS_FILE = "window_position.txt"
FONT_NAME = "IRANSansXFaNum"
FONT_SIZE = 11


class DateWidget(QWidget):
    """A draggable, frameless widget to display the Persian date."""

    def __init__(self):
        super().__init__()
        self.old_pos = None
        self.menu_is_open = False
        self.init_ui()
        self.load_position()

    def init_ui(self):
        """Initializes the user interface of the widget."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool  # Prevents the app from appearing in the taskbar
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel()
        font = QFont(FONT_NAME, FONT_SIZE)
        self.label.setFont(font)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            background-color: rgba(0, 0, 0, 0.01);
            color: white;
            padding: 10px;
            border-radius: 8px;
        """)

        layout.addWidget(self.label)

        self.update_time()

        self.date_update_timer = QTimer(self)
        self.date_update_timer.timeout.connect(self.update_time)
        self.date_update_timer.start(60000)

        if IS_WINDOWS:
            self.keep_on_top_timer = QTimer(self)
            self.keep_on_top_timer.timeout.connect(self.ensure_on_top_windows)
            self.keep_on_top_timer.start(2000)

    def ensure_on_top_windows(self):
        """
        Uses the Windows API to forcefully keep the window on top,
        but only if the context menu is not open.
        """
        if self.menu_is_open:
            return

        hwnd = self.winId()
        if hwnd:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )

    def update_time(self):
        """Updates the date and time text."""
        now = jdatetime.datetime.now()
        date_str = now.strftime("%Y/%m/%d")
        day_str = DAYS_IN_PERSIAN[now.strftime("%A")]
        self.label.setText(f"{day_str}\n{date_str}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.save_position()
            self.old_pos = None

    def contextMenuEvent(self, event):
        """Shows a context menu and flags its state."""
        context_menu = QMenu(self)
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        context_menu.addAction(exit_action)

        self.menu_is_open = True
        context_menu.exec(event.globalPos())
        self.menu_is_open = False

    def save_position(self):
        with open(WINDOW_POS_FILE, "w") as file:
            file.write(f"{self.pos().x()} {self.pos().y()}")

    def load_position(self):
        if os.path.exists(WINDOW_POS_FILE):
            try:
                with open(WINDOW_POS_FILE, "r") as file:
                    pos = file.read().split()
                    if len(pos) == 2:
                        self.move(int(pos[0]), int(pos[1]))
            except (ValueError, IndexError):
                print("Could not load window position.")

    def closeEvent(self, event):
        """Saves position and ensures the entire application quits."""
        self.save_position()
        # Explicitly quit the application's event loop
        QApplication.instance().quit()
        super().closeEvent(event)


def main():
    """Main function to run the application."""

    # This pattern (signal handler + QTimer) is a standard workaround
    # to ensure clean exit on Ctrl+C in IDEs.
    def sigint_handler(*args):
        QApplication.quit()

    signal.signal(signal.SIGINT, sigint_handler)

    app = QApplication(sys.argv)

    # This timer allows the Python interpreter to wake up and process signals.
    timer = QTimer()
    timer.start(100)
    timer.timeout.connect(lambda: None)

    widget = DateWidget()
    widget.show()

    exit_code = app.exec()
    print("برنامه با موفقیت بسته شد.")
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
