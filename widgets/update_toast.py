"""Lightweight, closable toast for update status (non-modal)."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QGuiApplication
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Informational toasts stay long enough to read comfortably.
INFO_TOAST_MS = 12_000
FAILED_TOAST_MS = 14_000


class UpdateToast(QWidget):
    """Compact card toast with an X close control and optional primary action."""

    def __init__(
        self,
        *,
        title: str,
        body_html: str,
        action_label: str | None = None,
        action_url: str | None = None,
        app_icon=None,
        parent=None,
        auto_close_ms: int | None = None,
        accept_focus: bool = False,
        on_dismissed=None,
    ):
        super().__init__(parent)
        self._action_url = action_url
        self._on_dismissed = on_dismissed
        self._dismiss_emitted = False
        self._suppress_dismiss = False
        self._auto_close_ms = auto_close_ms if auto_close_ms and auto_close_ms > 0 else None
        self._close_timer = QTimer(self)
        self._close_timer.setSingleShot(True)
        self._close_timer.timeout.connect(self.close)

        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        if not accept_focus:
            flags |= Qt.WindowType.WindowDoesNotAcceptFocus
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        if app_icon is not None:
            self.setWindowIcon(app_icon)

        self.setFixedWidth(380)
        self._build_ui(title, body_html, action_label)
        self.adjustSize()
        self._arm_auto_close()

    def _build_ui(self, title: str, body_html: str, action_label: str | None):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("updateToastCard")
        card.setStyleSheet(
            """
            QFrame#updateToastCard {
                background-color: #1E1E1E;
                border: 1px solid rgba(255, 255, 255, 0.18);
                border-radius: 10px;
            }
            QLabel#toastTitle {
                color: #FFFFFF;
                font-size: 12pt;
                font-weight: 600;
            }
            QLabel#toastBody {
                color: rgba(255, 255, 255, 0.82);
                font-size: 10pt;
            }
            QLabel#toastBody a {
                color: #6EA8FE;
                text-decoration: none;
                font-weight: 600;
            }
            QPushButton#toastClose {
                background: transparent;
                color: rgba(255, 255, 255, 0.7);
                border: none;
                font-size: 14pt;
                padding: 0 4px;
            }
            QPushButton#toastClose:hover {
                color: #FFFFFF;
            }
            QPushButton#toastAction {
                background-color: #2F6FED;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 14px;
                font-size: 10pt;
            }
            QPushButton#toastAction:hover {
                background-color: #3B7CFF;
            }
            """
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 12, 14, 14)
        card_layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("toastTitle")
        title_label.setWordWrap(True)

        close_btn = QPushButton("×")
        close_btn.setObjectName("toastClose")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setFlat(True)
        close_btn.setFixedSize(28, 28)
        close_btn.clicked.connect(self.close)
        close_btn.setToolTip("بستن")

        header.addWidget(title_label, stretch=1)
        header.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignTop)
        card_layout.addLayout(header)

        body_label = QLabel(body_html)
        body_label.setObjectName("toastBody")
        body_label.setWordWrap(True)
        body_label.setTextFormat(Qt.TextFormat.RichText)
        body_label.setOpenExternalLinks(False)
        body_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        body_label.linkActivated.connect(self._on_link_activated)
        card_layout.addWidget(body_label)

        if action_label and self._action_url:
            action_btn = QPushButton(action_label)
            action_btn.setObjectName("toastAction")
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.clicked.connect(self._open_action)
            card_layout.addWidget(action_btn, alignment=Qt.AlignmentFlag.AlignLeft)

        outer.addWidget(card)

    def _arm_auto_close(self):
        if self._auto_close_ms:
            self._close_timer.start(self._auto_close_ms)

    def enterEvent(self, event):
        # Pause dismiss while the user is reading / aiming at the link.
        if self._close_timer.isActive():
            self._close_timer.stop()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._arm_auto_close()
        super().leaveEvent(event)

    def suppress_dismiss_callback(self):
        """Used when replacing this toast programmatically (not a user dismiss)."""
        self._suppress_dismiss = True

    def _emit_dismissed(self):
        if self._suppress_dismiss or self._dismiss_emitted:
            return
        self._dismiss_emitted = True
        if self._on_dismissed is not None:
            try:
                self._on_dismissed()
            except Exception:
                pass

    def closeEvent(self, event):
        self._emit_dismissed()
        super().closeEvent(event)

    def _on_link_activated(self, link: str):
        QDesktopServices.openUrl(QUrl(link))
        self.close()

    def _open_action(self):
        if self._action_url:
            QDesktopServices.openUrl(QUrl(self._action_url))
        self.close()

    def show_near_bottom_right(self, margin: int = 18):
        """Places the toast above the taskbar on the primary screen."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.show()
            return
        geo = screen.availableGeometry()
        self.adjustSize()
        x = geo.right() - self.width() - margin
        y = geo.bottom() - self.height() - margin
        self.move(max(geo.left() + margin, x), max(geo.top() + margin, y))
        self.show()
        self.raise_()


def show_update_available_toast(
    *,
    local_version: str,
    remote_version: str,
    release_url: str,
    app_icon=None,
    parent=None,
    on_dismissed=None,
) -> UpdateToast:
    # Stays until the user closes it or opens the release page (no auto-dismiss).
    toast = UpdateToast(
        title="نسخه جدید آماده است",
        body_html=(
            f"نسخه <b>{remote_version}</b> منتشر شده است "
            f"(نسخه فعلی شما: {local_version}). "
            f'<a href="{release_url}">برای دریافت به‌روزرسانی اینجا کلیک کنید</a>.'
        ),
        action_label="دریافت به‌روزرسانی از گیت‌هاب",
        action_url=release_url,
        app_icon=app_icon,
        parent=parent,
        auto_close_ms=None,
        accept_focus=True,
        on_dismissed=on_dismissed,
    )
    toast.show_near_bottom_right()
    return toast


def show_up_to_date_toast(
    *,
    local_version: str,
    app_icon=None,
    parent=None,
) -> UpdateToast:
    toast = UpdateToast(
        title="برنامه به‌روز است",
        body_html=f"شما آخرین نسخه را دارید (نسخه {local_version}).",
        app_icon=app_icon,
        parent=parent,
        auto_close_ms=INFO_TOAST_MS,
    )
    toast.show_near_bottom_right()
    return toast


def show_update_check_failed_toast(*, app_icon=None, parent=None) -> UpdateToast:
    toast = UpdateToast(
        title="بررسی به‌روزرسانی انجام نشد",
        body_html=(
            "در حال حاضر امکان ارتباط با گیت‌هاب وجود ندارد. "
            "لطفاً اتصال اینترنت را بررسی کنید و دوباره تلاش کنید."
        ),
        app_icon=app_icon,
        parent=parent,
        auto_close_ms=FAILED_TOAST_MS,
    )
    toast.show_near_bottom_right()
    return toast
