import sys
import socket
import threading
import time
import json
import binascii
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QComboBox,
    QGroupBox,
    QCheckBox,
    QRadioButton,
    QTabWidget,
    QSplitter,
    QGridLayout,
    QListWidget,
    QMessageBox,
)
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, Qt
from PyQt5.QtGui import QColor, QTextCursor, QFont

from log_model import setup_logger


class Client(QObject):
    """
    Class quản lý kết nối TCP client.
    """

    # Định nghĩa signals
    connected = pyqtSignal(str, int)  # (host, port)
    disconnected = pyqtSignal()
    dataReceived = pyqtSignal(bytes)
    errorOccurred = pyqtSignal(str)  # error message

    def __init__(self):
        """
        Khởi tạo TCP Client.
        """
        super().__init__()
        self.socket = None
        self.connected_host = None
        self.connected_port = None
        self.is_connected = False
        self.receive_thread = None
        self.running = False

    def connect(self, host, port):
        """
        Kết nối tới server.

        Args:
            host (str): Địa chỉ server
            port (int): Cổng server

        Returns:
            bool: True nếu kết nối thành công, False nếu thất bại
        """
        if self.is_connected:
            self.disconnect()

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((host, port))
            self.is_connected = True
            self.connected_host = host
            self.connected_port = port
            self.running = True

            # Khởi động thread nhận dữ liệu
            self.receive_thread = threading.Thread(target=self._receive_data)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            self.connected.emit(host, port)
            return True

        except Exception as e:
            self.errorOccurred.emit(f"Lỗi kết nối: {str(e)}")
            self.socket = None
            return False

    def disconnect(self):
        """
        Ngắt kết nối.

        Returns:
            bool: True nếu ngắt kết nối thành công
        """
        self.running = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

            self.socket = None

        self.is_connected = False
        self.disconnected.emit()
        return True

    def send_data(self, data, as_hex=False):
        """
        Gửi dữ liệu tới server.

        Args:
            data: Dữ liệu cần gửi (str hoặc bytes)
            as_hex (bool): Nếu True, data là chuỗi hex cần chuyển đổi thành binary

        Returns:
            bool: True nếu gửi thành công, False nếu thất bại
        """
        if not self.is_connected or not self.socket:
            self.errorOccurred.emit("Chưa kết nối tới server")
            return False

        try:
            if as_hex:
                # Chuyển đổi chuỗi hex thành binary
                try:
                    # Xóa khoảng trắng
                    clean_hex = (
                        data.replace(" ", "").replace("\n", "").replace("\r", "")
                    )
                    # Chuyển đổi thành binary
                    binary_data = binascii.unhexlify(clean_hex)
                except Exception as e:
                    self.errorOccurred.emit(f"Lỗi chuyển đổi hex: {str(e)}")
                    return False
            else:
                # Chuyển đổi chuỗi thành binary nếu cần
                if isinstance(data, str):
                    binary_data = data.encode("utf-8")
                else:
                    binary_data = data

            # Gửi dữ liệu trực tiếp không thêm header length (phương thức Hercules)
            self.socket.sendall(binary_data)
            return True

        except Exception as e:
            self.errorOccurred.emit(f"Lỗi gửi dữ liệu: {str(e)}")
            # Nếu lỗi socket, ngắt kết nối
            if "Broken pipe" in str(e) or "Connection reset" in str(e):
                self.disconnect()
            return False

    # Phương thức nhận dữ liệu (sửa đổi) - tương thích với Hercules
    def _receive_data(self):
        """
        Thread nhận dữ liệu liên tục.
        """
        self.socket.settimeout(0.5)  # Timeout để kiểm tra trạng thái running

        while self.running and self.is_connected:
            try:
                # Nhận dữ liệu trực tiếp (phương thức Hercules)
                data = self.socket.recv(4096)

                if not data:  # Kết nối đã đóng
                    break

                # Phát signal cho dữ liệu nhận được
                self.dataReceived.emit(data)

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.errorOccurred.emit(f"Lỗi nhận dữ liệu: {str(e)}")
                    break

        # Kết nối đã đóng
        if self.is_connected:
            self.disconnect()

    def send_check(self):
        """
        Gửi lệnh "Check" tới server.

        Returns:
            bool: True nếu gửi thành công, False nếu thất bại
        """
        return self.send_data("Check")


class TCPClientApp(QMainWindow):
    """
    Ứng dụng TCP Client với giao diện tương tự Hercules.
    """

    def __init__(self):
        super().__init__()
        self.client = Client()
        self.setup_ui()
        self.connect_signals()
        self.last_send_data = ""  # Lưu trữ dữ liệu gửi gần nhất

    def setup_ui(self):
        """
        Thiết lập giao diện người dùng.
        """
        self.setWindowTitle("TCP Client")
        self.setGeometry(100, 100, 900, 600)

        # Widget chính
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Tạo splitter để chia màn hình thành hai phần
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)

        # Phần trên: Cấu hình kết nối và điều khiển
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)

        # Phần cấu hình kết nối
        connection_group = QGroupBox("Cấu hình kết nối")
        connection_layout = QGridLayout(connection_group)

        connection_layout.addWidget(QLabel("Host:"), 0, 0)
        self.host_input = QLineEdit("127.0.0.1")
        connection_layout.addWidget(self.host_input, 0, 1)

        connection_layout.addWidget(QLabel("Port:"), 0, 2)
        self.port_input = QLineEdit("8080")
        connection_layout.addWidget(self.port_input, 0, 3)

        self.connect_btn = QPushButton("Kết nối")
        self.connect_btn.setStyleSheet("background-color: green; color: white")
        connection_layout.addWidget(self.connect_btn, 0, 4)

        # Thêm nút Check
        self.check_btn = QPushButton("Check")
        self.check_btn.setEnabled(False)
        self.check_btn.setStyleSheet("background-color: blue; color: white")
        connection_layout.addWidget(self.check_btn, 0, 5)

        self.status_label = QLabel("Trạng thái: Chưa kết nối")
        connection_layout.addWidget(self.status_label, 1, 0, 1, 6)

        top_layout.addWidget(connection_group)

        # Phần gửi dữ liệu
        send_group = QGroupBox("Gửi dữ liệu")
        send_layout = QVBoxLayout(send_group)

        # Tab để chọn kiểu dữ liệu gửi
        self.send_tabs = QTabWidget()

        # Tab gửi văn bản
        text_tab = QWidget()
        text_layout = QVBoxLayout(text_tab)
        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("Nhập dữ liệu dạng văn bản để gửi...")
        text_layout.addWidget(self.text_input)
        self.send_tabs.addTab(text_tab, "Văn bản")

        # Tab gửi hex
        hex_tab = QWidget()
        hex_layout = QVBoxLayout(hex_tab)
        self.hex_input = QTextEdit()
        self.hex_input.setPlaceholderText(
            "Nhập dữ liệu dạng hex (VD: 48 65 6C 6C 6F)..."
        )
        hex_layout.addWidget(self.hex_input)
        self.send_tabs.addTab(hex_tab, "Hex")

        send_layout.addWidget(self.send_tabs)

        # Nút gửi dữ liệu
        send_btn_layout = QHBoxLayout()
        self.send_btn = QPushButton("Gửi")
        self.send_btn.setEnabled(False)
        send_btn_layout.addWidget(self.send_btn)

        self.repeat_check = QCheckBox("Lặp lại")
        send_btn_layout.addWidget(self.repeat_check)

        self.repeat_interval = QLineEdit("1000")
        self.repeat_interval.setFixedWidth(100)
        self.repeat_interval.setPlaceholderText("ms")
        send_btn_layout.addWidget(self.repeat_interval)
        send_btn_layout.addWidget(QLabel("ms"))

        self.send_cr = QCheckBox("Thêm CR (\\r)")
        self.send_lf = QCheckBox("Thêm LF (\\n)")
        self.send_cr.setChecked(True)
        send_btn_layout.addWidget(self.send_cr)
        send_btn_layout.addWidget(self.send_lf)

        send_layout.addLayout(send_btn_layout)

        top_layout.addWidget(send_group)

        # Thêm widget trên vào splitter
        splitter.addWidget(top_widget)

        # Phần dưới: Hiển thị log và dữ liệu nhận được
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)

        # Tab để chọn chế độ hiển thị
        self.view_tabs = QTabWidget()

        # Tab hiển thị dữ liệu dạng văn bản
        self.log_text = QListWidget()
        self.log_text.setAlternatingRowColors(True)
        self.view_tabs.addTab(self.log_text, "Log")

        # Tab hiển thị dữ liệu nhận dạng hex
        self.received_hex = QTextEdit()
        self.received_hex.setReadOnly(True)
        self.view_tabs.addTab(self.received_hex, "Dữ liệu nhận (Hex)")

        # Tab hiển thị dữ liệu nhận dạng văn bản
        self.received_text = QTextEdit()
        self.received_text.setReadOnly(True)
        self.view_tabs.addTab(self.received_text, "Dữ liệu nhận (Văn bản)")

        bottom_layout.addWidget(self.view_tabs)

        # Các tùy chọn hiển thị
        display_options = QHBoxLayout()

        self.clear_log_btn = QPushButton("Xóa log")
        display_options.addWidget(self.clear_log_btn)

        self.auto_scroll = QCheckBox("Tự động cuộn")
        self.auto_scroll.setChecked(True)
        display_options.addWidget(self.auto_scroll)

        self.timestamp = QCheckBox("Hiển thị thời gian")
        self.timestamp.setChecked(True)
        display_options.addWidget(self.timestamp)

        display_options.addStretch()
        bottom_layout.addLayout(display_options)

        # Thêm widget dưới vào splitter
        splitter.addWidget(bottom_widget)

        # Thiết lập tỷ lệ phân chia
        splitter.setSizes([300, 300])

        # Thiết lập logger
        self.logger, self.log_signals = setup_logger(self.log_text)

    def connect_signals(self):
        """
        Kết nối các signals và slots.
        """
        # Buttons
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.send_btn.clicked.connect(self.send_data)
        self.clear_log_btn.clicked.connect(self.clear_log)
        self.check_btn.clicked.connect(self.send_check)

        # Client signals
        self.client.connected.connect(self.on_connected)
        self.client.disconnected.connect(self.on_disconnected)
        self.client.dataReceived.connect(self.on_data_received)
        self.client.errorOccurred.connect(self.on_error)

        # Repeat timer
        self.repeat_timer = None
        self.repeat_check.stateChanged.connect(self.toggle_repeat)

    def toggle_connection(self):
        """
        Xử lý kết nối/ngắt kết nối.
        """
        if not self.client.is_connected:
            # Lấy host và port
            host = self.host_input.text().strip()
            try:
                port = int(self.port_input.text().strip())
            except ValueError:
                QMessageBox.warning(self, "Lỗi", "Port phải là số nguyên")
                return

            # Kết nối
            if self.client.connect(host, port):
                self.logger.info(f"Đang kết nối tới HOST: {host} - PORT: {port}...")
            else:
                self.logger.error(f"Không thể kết nối tới HOST: {host} - PORT: {port}")
        else:
            # Ngắt kết nối
            if self.client.disconnect():
                self.logger.info("Đã ngắt kết nối")

    def on_connected(self, host, port):
        """
        Xử lý khi kết nối thành công.
        """
        self.connect_btn.setText("Ngắt kết nối")
        self.connect_btn.setStyleSheet("background-color: red; color: white")
        self.status_label.setText(
            f"Trạng thái: Đã kết nối tới HOST: {host} - PORT: {port}"
        )
        self.send_btn.setEnabled(True)
        self.check_btn.setEnabled(True)
        self.logger.info(f"Đã kết nối tới HOST: {host} - PORT: {port}")

    def on_disconnected(self):
        """
        Xử lý khi ngắt kết nối.
        """
        self.connect_btn.setText("Kết nối")
        self.connect_btn.setStyleSheet("background-color: green; color: white")
        self.status_label.setText("Trạng thái: Chưa kết nối")
        self.send_btn.setEnabled(False)
        self.check_btn.setEnabled(False)

        # Dừng timer nếu đang chạy
        if self.repeat_timer:
            self.repeat_timer.cancel()
            self.repeat_timer = None
            self.repeat_check.setChecked(False)

    def send_check(self):
        """
        Gửi lệnh kiểm tra "Check" đến server.
        """
        if not self.client.is_connected:
            self.logger.warning("Chưa kết nối tới server")
            return

        if self.client.send_check():
            self.logger.info("Đã gửi lệnh Check tới server")
        else:
            self.logger.error("Không thể gửi lệnh Check")

    def on_data_received(self, data):
        """
        Xử lý khi nhận được dữ liệu.
        """
        # Hiển thị dạng hex
        hex_data = " ".join(f"{b:02X}" for b in data)

        if self.auto_scroll.isChecked():
            # Thêm vào cuối
            self.received_hex.append(hex_data)
            # Cuộn xuống dưới
            cursor = self.received_hex.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.received_hex.setTextCursor(cursor)
        else:
            # Thêm vào vị trí hiện tại
            cursor = self.received_hex.textCursor()
            cursor.insertText(hex_data + "\n")

        # Hiển thị dạng văn bản
        try:
            text_data = data.decode("utf-8")
        except UnicodeDecodeError:
            text_data = f"[Không thể hiển thị dạng văn bản] Hex: {hex_data}"

        if self.auto_scroll.isChecked():
            self.received_text.append(text_data)
            # Cuộn xuống dưới
            cursor = self.received_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.received_text.setTextCursor(cursor)
        else:
            # Thêm vào vị trí hiện tại
            cursor = self.received_text.textCursor()
            cursor.insertText(text_data)

        # Ghi log
        if self.timestamp.isChecked():
            self.logger.info(f"Nhận: {text_data}")
        else:
            self.log_signals.textSignal.emit(f"Nhận: {text_data}", "INFO")

    def on_error(self, message):
        """
        Xử lý khi có lỗi.
        """
        self.logger.error(message)

    def send_data(self):
        """
        Gửi dữ liệu.
        """
        current_tab = self.send_tabs.currentIndex()

        if current_tab == 0:  # Tab văn bản
            data = self.text_input.toPlainText()

            # Thêm CR/LF nếu cần
            if self.send_cr.isChecked():
                data += "\r"
            if self.send_lf.isChecked():
                data += "\n"

            if self.client.send_data(data):
                if self.timestamp.isChecked():
                    self.logger.info(f"Gửi: {data}")
                else:
                    self.log_signals.textSignal.emit(f"Gửi: {data}", "INFO")
                self.last_send_data = data

        else:  # Tab hex
            hex_data = self.hex_input.toPlainText()

            if self.client.send_data(hex_data, as_hex=True):
                if self.timestamp.isChecked():
                    self.logger.info(f"Gửi Hex: {hex_data}")
                else:
                    self.log_signals.textSignal.emit(f"Gửi Hex: {hex_data}", "INFO")
                self.last_send_data = hex_data

    def toggle_repeat(self, state):
        """
        Bật/tắt chế độ lặp lại gửi dữ liệu.
        """
        if state == Qt.Checked:
            # Kiểm tra xem đã kết nối chưa
            if not self.client.is_connected:
                self.logger.warning("Chưa kết nối. Không thể bật chế độ lặp lại.")
                self.repeat_check.setChecked(False)
                return

            # Lấy khoảng thời gian lặp lại
            try:
                interval = int(self.repeat_interval.text().strip())
                if interval < 100:  # Tối thiểu 100ms
                    interval = 100
                    self.repeat_interval.setText("100")
            except ValueError:
                self.logger.warning("Khoảng thời gian không hợp lệ")
                self.repeat_check.setChecked(False)
                return

            # Bắt đầu timer
            self.repeat_timer = threading.Timer(interval / 1000, self.repeat_send)
            self.repeat_timer.daemon = True
            self.repeat_timer.start()

            self.logger.info(f"Bắt đầu gửi lặp lại mỗi {interval}ms")
        else:
            # Dừng timer
            if self.repeat_timer:
                self.repeat_timer.cancel()
                self.repeat_timer = None
                self.logger.info("Đã dừng gửi lặp lại")

    def repeat_send(self):
        """
        Gửi dữ liệu lặp lại.
        """
        if not self.client.is_connected or not self.repeat_check.isChecked():
            return

        # Gửi dữ liệu
        self.send_data()

        # Lên lịch cho lần gửi tiếp theo
        try:
            interval = int(self.repeat_interval.text().strip())
            if interval < 100:
                interval = 100
        except ValueError:
            interval = 1000

        self.repeat_timer = threading.Timer(interval / 1000, self.repeat_send)
        self.repeat_timer.daemon = True
        self.repeat_timer.start()

    def clear_log(self):
        """
        Xóa log.
        """
        self.log_text.clear()
        self.received_hex.clear()
        self.received_text.clear()

    def closeEvent(self, event):
        """
        Xử lý khi đóng ứng dụng.
        """
        # Ngắt kết nối nếu đang kết nối
        if self.client.is_connected:
            self.client.disconnect()

        # Dừng timer nếu đang chạy
        if self.repeat_timer:
            self.repeat_timer.cancel()

        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TCPClientApp()
    window.show()
    sys.exit(app.exec_())
