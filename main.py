import sys
import os
import signal
import psutil

from PyQt6.QtWidgets import (QApplication, QWidget, QMenu, QHBoxLayout, QMessageBox,
                             QLabel, QDialog, QVBoxLayout, QPushButton)
from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QAction, QFontDatabase, QIcon, QDesktopServices

# --- Local Imports ---
from widgets.calendar_widget import CalendarWidget
from widgets.network_widget import NetworkWidget

# --- Windows-specific Imports ---
# Used for "Always on Top" and startup integration.
try:
    import win32gui
    import win32con
    import win32com.client
    import pythoncom
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False

# --- Constants ---
CONFIG_FILE = "config.txt"
APP_ICON_PATH = "icon.ico"
BASE_STYLESHEET = "QWidget { font-family: '%s'; }"


class MainWidget(QWidget):
    """The main widget that contains and manages all other components."""

    def __init__(self, font_name: str):
        super().__init__()
        self.font_name = font_name
        self.font_size = 10
        self.old_pos = None
        self.menu_is_open = False
        self.opacity_level = 0.6
        self.is_currently_in_startup = self._is_in_startup()

        if os.path.exists(APP_ICON_PATH):
            self.app_icon = QIcon(APP_ICON_PATH)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()
            print(f"Warning: Icon file not found at '{APP_ICON_PATH}'.")

        self.load_config()
        self.apply_global_font_size(self.font_size, initial=True)
        self.init_ui()

        if IS_WINDOWS:
            # Periodically force the window to stay on top.
            self.on_top_timer = QTimer(self)
            self.on_top_timer.timeout.connect(self.periodic_on_top_check)
            self.on_top_timer.start(1000)

    def init_ui(self):
        """Initializes the window and layout."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.background_widget = QWidget()
        self.update_background_style()

        container_layout = QHBoxLayout(self.background_widget)
        container_layout.setContentsMargins(10, 3, 10, 3)
        container_layout.setSpacing(10)

        self.calendar = CalendarWidget(parent=self)
        self.network = NetworkWidget(parent=self)

        container_layout.addWidget(self.calendar, alignment=Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(self.network, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.background_widget)

    def periodic_on_top_check(self):
        """Ensures the window stays on top, unless a menu is open."""
        if not self.menu_is_open:
            self.ensure_on_top_windows()

    def ensure_on_top_windows(self):
        """Uses win32gui to force the window to the topmost z-order."""
        if not IS_WINDOWS:
            return
        try:
            hwnd = self.winId()
            if hwnd:
                win32gui.SetWindowPos(int(hwnd), win32con.HWND_TOPMOST, 0, 0, 0, 0,
                                      win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
        except Exception:
            pass  # Fails silently if the window handle is not yet available.

    def update_background_style(self):
        """Updates the background color and opacity."""
        style = f"QWidget {{ background-color: rgba(20, 20, 20, {self.opacity_level}); border-radius: 8px; }}"
        self.background_widget.setStyleSheet(style)

    # --- Event Handlers for Window Dragging ---
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
            self.save_config()
            self.old_pos = None

    def contextMenuEvent(self, event):
        """Creates and displays the right-click context menu."""
        context_menu = QMenu(self)
        self.menu_is_open = True

        show_calendar_action = QAction("نمایش تقویم", self, checkable=True)
        show_calendar_action.setChecked(self.calendar.isVisible())
        show_calendar_action.toggled.connect(self._toggle_calendar_visibility)
        context_menu.addAction(show_calendar_action)

        show_network_action = QAction("نمایش سرعت شبکه", self, checkable=True)
        show_network_action.setChecked(self.network.isVisible())
        show_network_action.toggled.connect(self._toggle_network_visibility)
        context_menu.addAction(show_network_action)

        context_menu.addSeparator()

        font_menu = context_menu.addMenu("تغییر اندازه فونت")
        for size in range(9, 17):
            label = f"{size} pt (پیشفرض)" if size == 10 else f"{size} pt"
            action = QAction(label, self, checkable=True)
            action.setChecked(size == self.font_size)
            action.triggered.connect(lambda checked, s=size: self.apply_global_font_size(s))
            font_menu.addAction(action)

        opacity_menu = context_menu.addMenu("تنظیم شفافیت")
        opacities = {"0%": 0.01, "20%": 0.2, "40%": 0.4, "60%": 0.6, "80%": 0.8, "100%": 1.0}
        for label, value in opacities.items():
            display_label = f"{label} (پیشفرض)" if value == 0.6 else label
            action = QAction(display_label, self, checkable=True)
            action.setChecked(abs(value - self.opacity_level) < 0.01)
            action.triggered.connect(lambda checked, v=value: self.set_opacity(v))
            opacity_menu.addAction(action)

        update_interval_menu = context_menu.addMenu("تنظیم زمان‌بندی به‌روزرسانی")
        intervals = {"0.5 ثانیه": 500, "1 ثانیه": 1000, "1.5 ثانیه": 1500, "2 ثانیه": 2000, "2.5 ثانیه": 2500, "3 ثانیه": 3000}
        current_interval = self.network.timer.interval()
        for label, value in intervals.items():
            display_label = f"\u200f(پیشفرض) {label}" if value == 1000 else f"\u200f {label}"
            action = QAction(display_label, self, checkable=True)
            action.setChecked(value == current_interval)
            action.triggered.connect(lambda checked, v=value: self.network.set_update_interval(v))
            update_interval_menu.addAction(action)

        interface_menu = context_menu.addMenu("انتخاب اینترفیس شبکه")
        try:
            for iface in psutil.net_if_addrs().keys():
                action = QAction(iface, self, checkable=True)
                action.setChecked(iface == self.network.interface)
                action.triggered.connect(lambda checked, i=iface: self.network.set_interface(i))
                interface_menu.addAction(action)
        except Exception as e:
            interface_menu.addAction(QAction(f"Error: {e}", self, enabled=False))

        context_menu.addSeparator()

        if IS_WINDOWS:
            startup_action = QAction("اجرای خودکار هنگام شروع ویندوز", self, checkable=True)
            startup_action.setChecked(self.is_currently_in_startup)
            startup_action.toggled.connect(self._toggle_startup)
            context_menu.addAction(startup_action)
            context_menu.addSeparator()

        about_action = QAction("درباره برنامه", self)
        about_action.triggered.connect(self._show_about_dialog)
        context_menu.addAction(about_action)

        exit_action = QAction("خروج", self)
        exit_action.triggered.connect(self._quit_application)
        context_menu.addAction(exit_action)

        context_menu.exec(event.globalPos())
        self.menu_is_open = False

    def _toggle_calendar_visibility(self, visible):
        """Shows or hides the calendar widget."""
        if not visible and not self.network.isVisible():
            if sender := self.sender():
                sender.setChecked(True)
            self._show_error_message("حداقل یک ویجت باید فعال باشد.")
            return
        self.calendar.setVisible(visible)
        self.background_widget.adjustSize()
        self.adjustSize()

    def _toggle_network_visibility(self, visible):
        """Shows or hides the network widget."""
        if not visible and not self.calendar.isVisible():
            if sender := self.sender():
                sender.setChecked(True)
            self._show_error_message("حداقل یک ویجت باید فعال باشد.")
            return
        self.network.setVisible(visible)
        self.background_widget.adjustSize()
        self.adjustSize()

    def _get_startup_shortcut_path(self):
        """Gets the path for the application shortcut in the Windows Startup folder."""
        if not IS_WINDOWS:
            return None
        startup_folder = os.path.join(os.environ['APPDATA'], 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
        return os.path.join(startup_folder, "JalaliCalendarAndNetSpeed.lnk")

    def _is_in_startup(self):
        """Checks if the application is configured to run at startup."""
        path = self._get_startup_shortcut_path()
        return os.path.exists(path) if path else False

    def _toggle_startup(self, checked: bool):
        """Adds or removes the application from Windows startup."""
        if not IS_WINDOWS:
            return
        try:
            shortcut_path = self._get_startup_shortcut_path()
            if checked:
                target_path = os.path.abspath(sys.argv[0])
                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortCut(shortcut_path)
                shortcut.Targetpath = sys.executable if target_path.lower().endswith('.py') else target_path
                shortcut.Arguments = f'"{target_path}"' if target_path.lower().endswith('.py') else ''
                shortcut.WorkingDirectory = os.path.dirname(target_path)
                shortcut.IconLocation = os.path.abspath(APP_ICON_PATH) if os.path.exists(APP_ICON_PATH) else ''
                shortcut.save()
            elif os.path.exists(shortcut_path):
                os.remove(shortcut_path)
            self.is_currently_in_startup = checked
        except Exception as e:
            print(f"Error modifying startup settings: {e}")

    def set_opacity(self, level: float):
        """Sets the background opacity."""
        self.opacity_level = level
        self.update_background_style()

    def apply_global_font_size(self, size: int, initial: bool = False):
        """Applies a global font size to the application via stylesheets."""
        if not initial and size == self.font_size:
            return

        self.font_size = size
        font_stylesheet = f"font-size: {self.font_size}pt;"
        final_stylesheet = (BASE_STYLESHEET % self.font_name) + " QWidget { " + font_stylesheet + " }"
        QApplication.instance().setStyleSheet(final_stylesheet)

        if not initial:
            self.save_config()

        if hasattr(self, 'background_widget'):
            self.background_widget.adjustSize()
            self.adjustSize()

    def save_config(self):
        """Saves current settings to the config file."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(f"pos_x={self.pos().x()}\n")
                f.write(f"pos_y={self.pos().y()}\n")
                f.write(f"calendar_visible={self.calendar.isVisible()}\n")
                f.write(f"network_visible={self.network.isVisible()}\n")
                f.write(f"network_interface={self.network.interface or ''}\n")
                f.write(f"opacity={self.opacity_level}\n")
                f.write(f"network_interval={self.network.timer.interval()}\n")
                f.write(f"font_size={self.font_size}\n")
        except Exception as e:
            print(f"Error saving config: {e}")

    def load_config(self):
        """Loads settings from the config file on startup."""
        if not os.path.exists(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = {k: v for k, v in (line.strip().split("=", 1) for line in f if "=" in line)}
            self.move(int(config.get("pos_x", 100)), int(config.get("pos_y", 100)))
            self.font_size = int(config.get("font_size", 10))
            self.opacity_level = float(config.get("opacity", 0.6))

            # Defer applying some configs until widgets are fully initialized.
            def apply_late_configs():
                if hasattr(self, 'calendar'):
                    self.calendar.setVisible(config.get("calendar_visible", "True") == "True")
                    self.network.setVisible(config.get("network_visible", "True") == "True")
                    if config.get('network_interface'):
                        self.network.set_interface(config['network_interface'])
                    interval = int(config.get("network_interval", 1000))
                    self.network.set_update_interval(interval)
                    self.update_background_style()
                    self.background_widget.adjustSize()
                    self.adjustSize()

            QTimer.singleShot(10, apply_late_configs)
        except Exception as e:
            print(f"Error loading config: {e}")

    def _center_dialog(self, dialog):
        """Centers a given dialog on the primary screen."""
        screen_geometry = QApplication.primaryScreen().geometry()
        dialog.adjustSize()
        dialog_size = dialog.geometry()
        x = int(screen_geometry.center().x() - dialog_size.width() / 2)
        y = int(screen_geometry.center().y() - dialog_size.height() / 2)
        dialog.move(x, y)

    def _show_error_message(self, text: str):
        """Displays a modal error message."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("توجه")
        msg_box.setWindowIcon(self.app_icon)
        msg_box.setText(f"<div style='width: 450px;'><p style='font-size: 13pt;'>{text}</p></div>")
        msg_box.setStandardButtons(QMessageBox.StandardButton.NoButton)
        ok_button = QPushButton("تأیید")
        ok_button.clicked.connect(msg_box.accept)
        msg_box.addButton(ok_button, QMessageBox.ButtonRole.AcceptRole)
        self._center_dialog(msg_box)
        msg_box.exec()

    def _show_about_dialog(self):
        """Displays the 'About' dialog."""
        dialog = QDialog(self)
        dialog.setWindowTitle("درباره برنامه")
        dialog.setWindowIcon(self.app_icon)
        main_layout = QVBoxLayout()
        label = QLabel(
            """
            <div style='width: 450px;'>
                <p align="right" style="font-size:13pt;">برنامه نویس: آرمین نکوئی</p>
                <p align="right" style="font-size:13pt;">لینک سورس پروژه در گیت‌هاب:</p>
                <p align="left" style="font-size:11pt;"><a href='https://github.com/nekooee/PersianCalendarAndNetSpeed'>https://github.com/nekooee/PersianCalendarAndNetSpeed</a></p>
            </div>
            """
        )
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        label.setOpenExternalLinks(False)
        label.linkActivated.connect(lambda link: (QDesktopServices.openUrl(QUrl(link)), dialog.accept()))

        button_layout = QHBoxLayout()
        ok_button = QPushButton("تایید")
        ok_button.clicked.connect(dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addStretch()

        main_layout.addWidget(label)
        main_layout.addLayout(button_layout)
        dialog.setLayout(main_layout)
        self._center_dialog(dialog)
        dialog.exec()

    def _quit_application(self):
        """Stops all timers, saves config, and cleanly quits the application.
        This is connected to the 'Exit' action to ensure a clean shutdown.
        """
        self.network.timer.stop()
        if IS_WINDOWS:
            self.on_top_timer.stop()
        self.save_config()
        QApplication.instance().quit()


def main():
    # Initialize COM for win32com usage on Windows
    if IS_WINDOWS:
        pythoncom.CoInitialize()

    # Gracefully handle termination signals like Ctrl+C
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())

    app = QApplication(sys.argv)

    font_name = "Vazirmatn FD"
    try:
        # This block correctly resolves asset paths for both normal execution
        # and a PyInstaller single-file bundle.
        if getattr(sys, 'frozen', False):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        font_path = os.path.join(base_path, "fonts", "Vazirmatn-FD-Regular.ttf")

        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_name = QFontDatabase.applicationFontFamilies(font_id)[0]
                print(f"Font '{font_name}' loaded successfully.")
        else:
            print(f"Font file not found at: {font_path}")

        app.setStyleSheet(BASE_STYLESHEET % font_name)

    except Exception as e:
        print(f"An unexpected error occurred while setting the font: {e}")

    widget = MainWidget(font_name=font_name)
    widget.show()

    try:
        sys.exit(app.exec())
    finally:
        # Uninitialize COM before exiting
        if IS_WINDOWS:
            pythoncom.CoUninitialize()


if __name__ == '__main__':
    main()