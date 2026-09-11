import sys
import os
import json
import signal
import psutil

from PyQt6.QtWidgets import (QApplication, QWidget, QMenu, QHBoxLayout, QMessageBox,
                             QLabel, QDialog, QVBoxLayout, QPushButton, QColorDialog,
                             QFontDialog)
from PyQt6.QtCore import QTimer, Qt, QUrl
from PyQt6.QtGui import QAction, QFontDatabase, QIcon, QDesktopServices, QColor, QFont

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
APP_VERSION = "1.1.3"
APP_ICON_PATH = "icon.ico"
CONFIG_FILENAME = "config.json"
LEGACY_CONFIG_FILENAME = "config.txt"
BASE_STYLESHEET = "QWidget { font-family: '%s'; }"
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_BG_COLOR = "#141414"
DEFAULT_FONT_SIZE = 10
DEFAULT_OPACITY = 0.6
DEFAULT_NETWORK_INTERVAL = 1000


def get_app_base_path() -> str:
    """Asset path for bundled resources (fonts/icon)."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.abspath(".")


def get_config_dir() -> str:
    """Directory where config.json should live (next to exe/script)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path(*, for_write: bool = False) -> str:
    """Returns path for config.json. Writes always go next to the app."""
    preferred = os.path.join(get_config_dir(), CONFIG_FILENAME)
    if for_write or os.path.exists(preferred):
        return preferred
    cwd_json = os.path.join(os.path.abspath("."), CONFIG_FILENAME)
    if os.path.exists(cwd_json) and os.path.normpath(cwd_json) != os.path.normpath(preferred):
        return cwd_json
    return preferred


def get_legacy_config_path() -> str | None:
    """Finds an old config.txt if present (for one-time migration)."""
    candidates = [
        os.path.join(get_config_dir(), LEGACY_CONFIG_FILENAME),
        os.path.join(os.path.abspath("."), LEGACY_CONFIG_FILENAME),
    ]
    seen = set()
    for path in candidates:
        normalized = os.path.normpath(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.exists(path):
            return path
    return None


def load_legacy_txt_config(path: str) -> dict:
    """Parses legacy key=value config.txt into a dict with typed values."""
    with open(path, "r", encoding="utf-8") as f:
        raw = {k: v for k, v in (line.strip().split("=", 1) for line in f if "=" in line)}

    def as_bool(value, default=True):
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    config = {
        "pos_x": int(raw.get("pos_x", 100)),
        "pos_y": int(raw.get("pos_y", 100)),
        "calendar_visible": as_bool(raw.get("calendar_visible"), True),
        "network_visible": as_bool(raw.get("network_visible"), True),
        "network_interface": raw.get("network_interface", "") or "",
        "opacity": float(raw.get("opacity", DEFAULT_OPACITY)),
        "network_interval": int(raw.get("network_interval", DEFAULT_NETWORK_INTERVAL)),
        "font_size": int(raw.get("font_size", DEFAULT_FONT_SIZE)),
        "font_name": raw.get("font_name") or None,
        "text_color": raw.get("text_color", DEFAULT_TEXT_COLOR),
        "bg_color": raw.get("bg_color", DEFAULT_BG_COLOR),
    }
    return config


def resolve_default_font_name(fallback: str = "Vazirmatn FD") -> str:
    """Loads the bundled Persian font when available and returns its family name."""
    font_path = os.path.join(get_app_base_path(), "fonts", "Vazirmatn-FD-Regular.ttf")
    if os.path.exists(font_path):
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
    return fallback


class MainWidget(QWidget):
    """The main widget that contains and manages all other components."""

    def __init__(self, font_name: str):
        super().__init__()
        self.font_name = font_name
        self.font_size = DEFAULT_FONT_SIZE
        self.text_color = DEFAULT_TEXT_COLOR
        self.bg_color = DEFAULT_BG_COLOR
        self.old_pos = None
        self.menu_is_open = False
        self.opacity_level = DEFAULT_OPACITY
        self.is_currently_in_startup = self._is_in_startup()
        self._pending_config = {}

        # Correctly resolve paths for both bundled exe and normal script
        base_path = get_app_base_path()
        icon_full_path = os.path.join(base_path, APP_ICON_PATH)

        if os.path.exists(icon_full_path):
            self.app_icon = QIcon(icon_full_path)
            self.setWindowIcon(self.app_icon)
        else:
            self.app_icon = QIcon()
            print(f"Warning: Icon file not found at '{icon_full_path}'.")

        self.load_config()
        self.apply_global_font(initial=True)
        self.init_ui()
        self._apply_pending_config()
        # Ensure config.json is created/updated as soon as the app is ready.
        QTimer.singleShot(0, self.save_config)

        if IS_WINDOWS:
            # Periodically ensure the widget remains on top of other windows.
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
        self.apply_text_color()

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
        color = QColor(self.bg_color)
        style = (
            f"QWidget {{ background-color: rgba({color.red()}, {color.green()}, "
            f"{color.blue()}, {self.opacity_level}); border-radius: 8px; }}"
        )
        self.background_widget.setStyleSheet(style)

    def apply_text_color(self):
        """Applies the current text color to calendar and network widgets."""
        if hasattr(self, 'calendar'):
            self.calendar.set_text_color(self.text_color)
        if hasattr(self, 'network'):
            self.network.set_text_color(self.text_color)

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

        appearance_menu = context_menu.addMenu("ظاهر")

        text_color_action = QAction("رنگ متن…", self)
        text_color_action.triggered.connect(self._choose_text_color)
        appearance_menu.addAction(text_color_action)

        bg_color_action = QAction("رنگ پس‌زمینه…", self)
        bg_color_action.triggered.connect(self._choose_background_color)
        appearance_menu.addAction(bg_color_action)

        font_action = QAction("فونت…", self)
        font_action.triggered.connect(self._choose_font)
        appearance_menu.addAction(font_action)

        appearance_menu.addSeparator()

        font_menu = appearance_menu.addMenu("اندازه فونت")
        for size in range(9, 17):
            label = f"{size} pt (پیشفرض)" if size == DEFAULT_FONT_SIZE else f"{size} pt"
            action = QAction(label, self, checkable=True)
            action.setChecked(size == self.font_size)
            action.triggered.connect(lambda checked, s=size: self.apply_global_font_size(s))
            font_menu.addAction(action)

        opacity_menu = appearance_menu.addMenu("شفافیت پس‌زمینه")
        opacities = {"0%": 0.01, "20%": 0.2, "40%": 0.4, "60%": 0.6, "80%": 0.8, "100%": 1.0}
        for label, value in opacities.items():
            display_label = f"{label} (پیشفرض)" if value == DEFAULT_OPACITY else label
            action = QAction(display_label, self, checkable=True)
            action.setChecked(abs(value - self.opacity_level) < 0.01)
            action.triggered.connect(lambda checked, v=value: self.set_opacity(v))
            opacity_menu.addAction(action)

        reset_appearance_action = QAction("بازنشانی ظاهر", self)
        reset_appearance_action.triggered.connect(self._reset_appearance)
        appearance_menu.addAction(reset_appearance_action)

        update_interval_menu = context_menu.addMenu("تنظیم زمان‌بندی به‌روزرسانی")
        intervals = {"0.5 ثانیه": 500, "1 ثانیه": 1000, "1.5 ثانیه": 1500, "2 ثانیه": 2000, "2.5 ثانیه": 2500, "3 ثانیه": 3000}
        current_interval = self.network.timer.interval()
        for label, value in intervals.items():
            display_label = f"\u200f(پیشفرض) {label}" if value == DEFAULT_NETWORK_INTERVAL else f"\u200f {label}"
            action = QAction(display_label, self, checkable=True)
            action.setChecked(value == current_interval)
            action.triggered.connect(lambda checked, v=value: self._set_network_interval(v))
            update_interval_menu.addAction(action)

        interface_menu = context_menu.addMenu("انتخاب اینترفیس شبکه")
        try:
            for iface in psutil.net_if_addrs().keys():
                action = QAction(iface, self, checkable=True)
                action.setChecked(iface == self.network.interface)
                action.triggered.connect(lambda checked, i=iface: self._set_network_interface(i))
                interface_menu.addAction(action)
        except Exception as e:
            interface_menu.addAction(QAction(f"Error: {e}", self, enabled=False))

        context_menu.addSeparator()

        reset_all_action = QAction("بازنشانی به تنظیمات پیش‌فرض", self)
        reset_all_action.triggered.connect(self._reset_all_settings)
        context_menu.addAction(reset_all_action)

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
        self.save_config()

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
        self.save_config()

    def _set_network_interface(self, interface_name: str):
        """Sets the monitored network interface and persists the choice."""
        self.network.set_interface(interface_name)
        self.save_config()

    def _set_network_interval(self, ms: int):
        """Sets the network update interval and persists the choice."""
        self.network.set_update_interval(ms)
        self.save_config()

    def _choose_text_color(self):
        """Opens a color dialog for text color."""
        initial = QColor(self.text_color)
        color = QColorDialog.getColor(initial, self, "انتخاب رنگ متن")
        if color.isValid():
            self.text_color = color.name()
            self.apply_text_color()
            self.save_config()

    def _choose_background_color(self):
        """Opens a color dialog for background color."""
        initial = QColor(self.bg_color)
        color = QColorDialog.getColor(initial, self, "انتخاب رنگ پس‌زمینه")
        if color.isValid():
            self.bg_color = color.name()
            self.update_background_style()
            self.save_config()

    def _choose_font(self):
        """Opens a font dialog for family and size."""
        current = QFont(self.font_name, self.font_size)
        font, ok = QFontDialog.getFont(current, self, "انتخاب فونت")
        if ok:
            self.font_name = font.family()
            self.font_size = font.pointSize() if font.pointSize() > 0 else DEFAULT_FONT_SIZE
            self.apply_global_font()
            self.save_config()

    def _reset_appearance(self):
        """Resets appearance settings to defaults."""
        self.text_color = DEFAULT_TEXT_COLOR
        self.bg_color = DEFAULT_BG_COLOR
        self.opacity_level = DEFAULT_OPACITY
        self.font_size = DEFAULT_FONT_SIZE
        self.font_name = resolve_default_font_name(self.font_name)
        self.apply_global_font()
        self.apply_text_color()
        self.update_background_style()
        self.save_config()

    def _reset_all_settings(self):
        """Resets all app settings to factory defaults and saves them."""
        self._reset_appearance()
        self.calendar.setVisible(True)
        self.network.setVisible(True)
        self.network.set_update_interval(DEFAULT_NETWORK_INTERVAL)
        default_iface = self.network.get_default_interface()
        if default_iface:
            self.network.set_interface(default_iface)
        self.background_widget.adjustSize()
        self.adjustSize()

        screen_geometry = QApplication.primaryScreen().geometry()
        self.move(screen_geometry.left() + 5, screen_geometry.bottom() - self.height() - 5)
        self.save_config()

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
        if not IS_WINDOWS:
            return
        try:
            shortcut_path = self._get_startup_shortcut_path()
            if checked:
                from win32com.client import gencache
                base_path = get_app_base_path()

                target_path = os.path.abspath(sys.argv[0])
                icon_full_path = os.path.join(base_path, APP_ICON_PATH)

                shell = gencache.EnsureDispatch('WScript.Shell')
                shortcut = shell.CreateShortcut(shortcut_path)
                shortcut.TargetPath = sys.executable if target_path.lower().endswith('.py') else target_path
                shortcut.Arguments = f'"{target_path}"' if target_path.lower().endswith('.py') else ''
                shortcut.WorkingDirectory = os.path.dirname(target_path)
                shortcut.IconLocation = icon_full_path if os.path.exists(icon_full_path) else ''
                shortcut.Save()

            elif os.path.exists(shortcut_path):
                os.remove(shortcut_path)
            self.is_currently_in_startup = checked
        except Exception as e:
            print(f"Error modifying startup settings: {e}")

    def set_opacity(self, level: float):
        """Sets the background opacity."""
        self.opacity_level = level
        self.update_background_style()
        self.save_config()

    def apply_global_font_size(self, size: int, initial: bool = False):
        """Applies a global font size to the application via stylesheets."""
        if not initial and size == self.font_size:
            return
        self.font_size = size
        self.apply_global_font(initial=initial)

    def apply_global_font(self, initial: bool = False):
        """Applies the current font family and size globally."""
        safe_family = self.font_name.replace("'", "\\'")
        final_stylesheet = (
            f"QWidget {{ font-family: '{safe_family}'; font-size: {self.font_size}pt; }}"
        )
        QApplication.instance().setStyleSheet(final_stylesheet)

        if not initial:
            self.save_config()

        if hasattr(self, 'background_widget'):
            self.background_widget.adjustSize()
            self.adjustSize()

    def save_config(self):
        """Saves current settings to config.json next to the app."""
        config = {
            "pos_x": self.pos().x(),
            "pos_y": self.pos().y(),
            "calendar_visible": self.calendar.isVisible() if hasattr(self, 'calendar') else True,
            "network_visible": self.network.isVisible() if hasattr(self, 'network') else True,
            "network_interface": (self.network.interface or '') if hasattr(self, 'network') else '',
            "opacity": self.opacity_level,
            "network_interval": (
                self.network.timer.interval() if hasattr(self, 'network') else DEFAULT_NETWORK_INTERVAL
            ),
            "font_size": self.font_size,
            "font_name": self.font_name,
            "text_color": self.text_color,
            "bg_color": self.bg_color,
        }
        path = get_config_path(for_write=True)
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            print(f"Error saving config to '{path}': {e}")

    def load_config(self):
        """Loads settings from config.json (or migrates legacy config.txt)."""
        config_path = get_config_path()
        config = None

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as e:
                print(f"Error loading config.json: {e}")
        else:
            legacy_path = get_legacy_config_path()
            if legacy_path:
                try:
                    config = load_legacy_txt_config(legacy_path)
                except Exception as e:
                    print(f"Error migrating legacy config: {e}")

        if not config:
            def set_initial_position():
                screen_geometry = QApplication.primaryScreen().geometry()
                self.move(screen_geometry.left() + 5, screen_geometry.bottom() - self.height() - 5)
                self.save_config()

            QTimer.singleShot(0, set_initial_position)
            return

        try:
            self.move(int(config.get("pos_x", 100)), int(config.get("pos_y", 100)))
            self.font_size = int(config.get("font_size", DEFAULT_FONT_SIZE))
            self.opacity_level = float(config.get("opacity", DEFAULT_OPACITY))
            self.text_color = config.get("text_color", DEFAULT_TEXT_COLOR) or DEFAULT_TEXT_COLOR
            self.bg_color = config.get("bg_color", DEFAULT_BG_COLOR) or DEFAULT_BG_COLOR
            if config.get("font_name"):
                self.font_name = config["font_name"]
            self._pending_config = config
        except Exception as e:
            print(f"Error applying config: {e}")

    def _as_bool(self, value, default=True):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _apply_pending_config(self):
        """Applies settings that require widgets to already exist."""
        config = self._pending_config
        if not config:
            return

        self.calendar.setVisible(self._as_bool(config.get("calendar_visible"), True))
        self.network.setVisible(self._as_bool(config.get("network_visible"), True))

        saved_iface = str(config.get("network_interface", "") or "").strip()
        if saved_iface:
            available = set(psutil.net_if_addrs().keys())
            if saved_iface in available:
                self.network.set_interface(saved_iface)

        try:
            interval = int(config.get("network_interval", DEFAULT_NETWORK_INTERVAL))
            self.network.set_update_interval(interval)
        except (TypeError, ValueError):
            pass

        self.apply_text_color()
        self.update_background_style()
        self.background_widget.adjustSize()
        self.adjustSize()
        self._pending_config = {}

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
            f"""
            <div style='width: 450px;'>
                <p align="right" style="font-size:13pt;">نسخه: {APP_VERSION}</p>
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

    def closeEvent(self, event):
        """Persist settings even if the window is closed outside the Exit menu."""
        self.save_config()
        super().closeEvent(event)

def main():
    # Initialize COM for win32com usage on Windows
    if IS_WINDOWS:
        pythoncom.CoInitialize()

    # Gracefully handle termination signals like Ctrl+C
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())

    app = QApplication(sys.argv)
    app.setApplicationVersion(APP_VERSION)

    font_name = "Vazirmatn FD"
    try:
        font_name = resolve_default_font_name(font_name)
        app.setStyleSheet(BASE_STYLESHEET % font_name)
        print(f"Font '{font_name}' ready.")
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
