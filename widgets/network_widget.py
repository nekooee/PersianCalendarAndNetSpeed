import time
import psutil
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer


class NetworkWidget(QWidget):
    """A widget for displaying network download and upload speeds."""

    def __init__(self, parent=None):
        """Initializes the widget."""
        super().__init__(parent)
        self.last_check_time = time.time()
        self.last_bytes_sent = 0
        self.last_bytes_recv = 0
        self.interface = self.get_default_interface()
        self.init_ui()
        self.update_speed()

    def get_default_interface(self):
        """Finds a suitable active network interface to monitor."""
        try:
            stats = psutil.net_if_stats()
            active_interfaces = [
                iface for iface, data in stats.items()
                if data.isup and 'loopback' not in iface.lower() and 'virtual' not in iface.lower()
            ]
            if not active_interfaces:
                return None

            # Prioritize common interface names like Wi-Fi and Ethernet
            for priority in ['wi-fi', 'wlan', 'ethernet']:
                for iface in active_interfaces:
                    if priority in iface.lower():
                        chosen_interface = iface
                        # Initialize counters for the chosen interface
                        counters = psutil.net_io_counters(pernic=True).get(chosen_interface)
                        if counters:
                            self.last_bytes_sent = counters.bytes_sent
                            self.last_bytes_recv = counters.bytes_recv
                        return chosen_interface

            # If no priority interface is found, pick the first active one
            return active_interfaces[0]
        except Exception:
            return None

    def init_ui(self):
        """Initializes the widget's UI."""
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        common_style = "background-color: transparent; color: white; padding: 0px 0px;"

        self.download_label = QLabel("↓ 0.0 KB/s")
        self.download_label.setStyleSheet(common_style)
        self.download_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.upload_label = QLabel("↑ 0.0 KB/s")
        self.upload_label.setStyleSheet(common_style)
        self.upload_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(self.download_label)
        layout.addWidget(self.upload_label)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_speed)
        self.timer.start(1000)

    def format_speed(self, speed_bytes_per_sec):
        """Formats speed in bytes/sec into a human-readable string (KB/s, MB/s)."""
        if speed_bytes_per_sec < 1024:
            return f"{speed_bytes_per_sec:.1f} B/s"
        elif speed_bytes_per_sec < 1024 * 1024:
            return f"{speed_bytes_per_sec / 1024:.1f} KB/s"
        else:
            return f"{speed_bytes_per_sec / (1024 * 1024):.2f} MB/s"

    def update_speed(self):
        """Calculates and displays the current network speed."""
        if not self.interface:
            self.download_label.setText("↓ --")
            self.upload_label.setText("↑ --")
            return

        try:
            current_time = time.time()
            io_counters = psutil.net_io_counters(pernic=True).get(self.interface)
            if not io_counters:
                self.download_label.setText("↓ N/A")
                self.upload_label.setText("↑ N/A")
                return

            time_delta = current_time - self.last_check_time
            if time_delta == 0:
                return

            bytes_recv = io_counters.bytes_recv
            bytes_sent = io_counters.bytes_sent

            # Calculate speed only after the first data point is gathered
            if self.last_bytes_recv > 0:
                download_speed = (bytes_recv - self.last_bytes_recv) / time_delta
                self.download_label.setText(f"↓ {self.format_speed(download_speed)}")

            if self.last_bytes_sent > 0:
                upload_speed = (bytes_sent - self.last_bytes_sent) / time_delta
                self.upload_label.setText(f"↑ {self.format_speed(upload_speed)}")

            self.last_bytes_recv = bytes_recv
            self.last_bytes_sent = bytes_sent
            self.last_check_time = current_time

        except (KeyError, Exception):
            self.download_label.setText("↓ Error")
            self.upload_label.setText("↑ Error")

    def set_interface(self, interface_name):
        """Sets the network interface to monitor."""
        self.interface = interface_name
        # Reset counters to start fresh with the new interface
        self.last_bytes_sent = 0
        self.last_bytes_recv = 0
        self.last_check_time = time.time()
        # Update speed immediately to reflect the change
        self.update_speed()

    def set_update_interval(self, ms: int):
        """Changes the speed update interval."""
        if self.timer:
            self.timer.start(ms)