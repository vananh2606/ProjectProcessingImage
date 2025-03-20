import sys
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QMenu,
    QAction,
)
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QColor
from tcp_server import Server  # Import class Server đã cập nhật


class ServerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TCP Server với khóa client")
        self.resize(800, 600)
        self.initUI()

        # Khởi tạo server
        self.server = Server()
        self.setupServerSignals()

    def initUI(self):
        # Widget chính
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout chính
        main_layout = QVBoxLayout(central_widget)

        # Cấu hình server
        server_config_layout = QHBoxLayout()
        server_config_layout.addWidget(QLabel("Host:"))
        self.host_input = QLineEdit("127.0.0.1")
        server_config_layout.addWidget(self.host_input)

        server_config_layout.addWidget(QLabel("Port:"))
        self.port_input = QLineEdit("8080")
        server_config_layout.addWidget(self.port_input)

        self.start_button = QPushButton("Khởi động")
        self.start_button.clicked.connect(self.startServer)
        server_config_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Dừng")
        self.stop_button.clicked.connect(self.stopServer)
        self.stop_button.setEnabled(False)
        server_config_layout.addWidget(self.stop_button)

        main_layout.addLayout(server_config_layout)

        # Danh sách client
        main_layout.addWidget(QLabel("Danh sách client:"))
        self.client_table = QTableWidget(0, 3)  # 3 cột: host, address, actions
        self.client_table.setHorizontalHeaderLabels(["Host", "Address", "Hành động"])
        self.client_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.client_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.client_table.customContextMenuRequested.connect(self.showClientContextMenu)
        main_layout.addWidget(self.client_table)

        # Trạng thái khóa
        self.lock_status_layout = QHBoxLayout()
        self.lock_status_label = QLabel("Trạng thái: Không khóa")
        self.lock_status_layout.addWidget(self.lock_status_label)

        self.unlock_button = QPushButton("Mở khóa")
        self.unlock_button.clicked.connect(self.unlockServer)
        self.unlock_button.setEnabled(False)
        self.lock_status_layout.addWidget(self.unlock_button)

        main_layout.addLayout(self.lock_status_layout)

        # Vùng gửi dữ liệu
        main_layout.addWidget(QLabel("Gửi dữ liệu:"))
        self.data_input = QTextEdit()
        self.data_input.setPlaceholderText("Nhập dữ liệu cần gửi...")
        self.data_input.setMaximumHeight(100)
        main_layout.addWidget(self.data_input)

        send_layout = QHBoxLayout()
        self.send_all_button = QPushButton("Gửi tới tất cả")
        self.send_all_button.clicked.connect(self.sendToAll)
        send_layout.addWidget(self.send_all_button)

        main_layout.addLayout(send_layout)

        # Log
        main_layout.addWidget(QLabel("Log:"))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        main_layout.addWidget(self.log_display)

    def setupServerSignals(self):
        # Kết nối các signals từ server tới GUI
        self.server.serverStarted.connect(self.onServerStarted)
        self.server.serverStopped.connect(self.onServerStopped)
        self.server.clientConnected.connect(self.onClientConnected)
        self.server.clientDisconnected.connect(self.onClientDisconnected)
        self.server.dataReceived.connect(self.onDataReceived)
        # Kết nối signals mới của lock client
        self.server.clientLocked.connect(self.onClientLocked)
        self.server.clientUnlocked.connect(self.onClientUnlocked)

    @pyqtSlot()
    def startServer(self):
        host = self.host_input.text()
        try:
            port = int(self.port_input.text())
        except ValueError:
            self.log("Cổng không hợp lệ", "ERROR")
            return

        # Cập nhật thông tin server
        self.server.host = host
        self.server.port = port

        # Khởi động server
        if self.server.start():
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

    @pyqtSlot()
    def stopServer(self):
        self.server.stop()

    @pyqtSlot(str, int)
    def onServerStarted(self, host, port):
        self.log(f"Server khởi động tại {host}:{port}", "INFO")

    @pyqtSlot()
    def onServerStopped(self):
        self.log("Server đã dừng", "INFO")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.unlock_button.setEnabled(False)
        self.lock_status_label.setText("Trạng thái: Không khóa")
        # Xóa tất cả client khỏi bảng
        self.client_table.setRowCount(0)

    @pyqtSlot(str, str)
    def onClientConnected(self, host, address):
        self.log(f"Client kết nối {host}:{address}", "INFO")
        self.addClientToTable(host, address)

    @pyqtSlot(str, str)
    def onClientDisconnected(self, host, address):
        self.log(f"Client ngắt kết nối {host}:{address}", "INFO")
        self.removeClientFromTable(host, address)

    @pyqtSlot(str, str, str)
    def onDataReceived(self, host, address, data):
        self.log(f"Nhận từ {host}:{address}: {data}", "INFO")

    @pyqtSlot(str, str)
    def onClientLocked(self, host, address):
        self.log(f"Đã khóa server với client {host}:{address}", "INFO")
        self.lock_status_label.setText(f"Trạng thái: Khóa với {host}:{address}")
        self.unlock_button.setEnabled(True)

        # Cập nhật hiển thị bảng client (highlight client đang khóa)
        self.updateClientTableLockStatus(host, address)

    @pyqtSlot()
    def onClientUnlocked(self):
        self.log("Đã mở khóa server", "INFO")
        self.lock_status_label.setText("Trạng thái: Không khóa")
        self.unlock_button.setEnabled(False)

        # Cập nhật hiển thị bảng (bỏ highlight)
        self.updateClientTableLockStatus(None, None)

    def addClientToTable(self, host, address):
        row_position = self.client_table.rowCount()
        self.client_table.insertRow(row_position)

        # Thêm thông tin client
        self.client_table.setItem(row_position, 0, QTableWidgetItem(host))
        self.client_table.setItem(row_position, 1, QTableWidgetItem(address))

        # Thêm nút hành động
        lock_button = QPushButton("Khóa")
        lock_button.setProperty("host", host)
        lock_button.setProperty("address", address)
        lock_button.clicked.connect(self.lockToClient)

        send_button = QPushButton("Gửi")
        send_button.setProperty("host", host)
        send_button.setProperty("address", address)
        send_button.clicked.connect(self.sendToClient)

        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.addWidget(lock_button)
        action_layout.addWidget(send_button)
        action_layout.setContentsMargins(0, 0, 0, 0)

        self.client_table.setCellWidget(row_position, 2, action_widget)

    def removeClientFromTable(self, host, address):
        for row in range(self.client_table.rowCount()):
            if (
                self.client_table.item(row, 0).text() == host
                and self.client_table.item(row, 1).text() == address
            ):
                self.client_table.removeRow(row)
                break

    def updateClientTableLockStatus(self, host, address):
        # Cập nhật màu nền của client trong bảng
        for row in range(self.client_table.rowCount()):
            current_host = self.client_table.item(row, 0).text()
            current_address = self.client_table.item(row, 1).text()

            if host and address and current_host == host and current_address == address:
                # Highlight client đang khóa
                self.client_table.item(row, 0).setBackground(QColor(200, 255, 200))
                self.client_table.item(row, 1).setBackground(QColor(200, 255, 200))

                # Cập nhật các nút tương tác
                action_widget = self.client_table.cellWidget(row, 2)
                if action_widget:
                    layout = action_widget.layout()
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if isinstance(widget, QPushButton) and widget.text() == "Khóa":
                            widget.setText("Đã khóa")
                            widget.setEnabled(False)
            else:
                # Bỏ highlight cho các client khác
                if self.client_table.item(row, 0):
                    self.client_table.item(row, 0).setBackground(QColor(255, 255, 255))
                if self.client_table.item(row, 1):
                    self.client_table.item(row, 1).setBackground(QColor(255, 255, 255))

                # Cập nhật các nút tương tác
                action_widget = self.client_table.cellWidget(row, 2)
                if action_widget:
                    layout = action_widget.layout()
                    for i in range(layout.count()):
                        widget = layout.itemAt(i).widget()
                        if (
                            isinstance(widget, QPushButton)
                            and widget.text() == "Đã khóa"
                        ):
                            widget.setText("Khóa")
                            widget.setEnabled(True)

    @pyqtSlot()
    def lockToClient(self):
        button = self.sender()
        if not button:
            return

        host = button.property("host")
        address = button.property("address")

        if not host or not address:
            return

        client_info = (host, int(address))

        # Xác nhận khóa
        reply = QMessageBox.question(
            self,
            "Xác nhận khóa",
            f"Bạn có chắc chắn muốn khóa server với client {host}:{address}?\n\n"
            "Tất cả các client khác sẽ bị ngắt kết nối và không thể có client mới kết nối.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.server.lock_to_client(client_info)

    @pyqtSlot()
    def unlockServer(self):
        # Xác nhận mở khóa
        reply = QMessageBox.question(
            self,
            "Xác nhận mở khóa",
            "Bạn có chắc chắn muốn mở khóa server để cho phép nhiều client kết nối?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.server.unlock_client()

    @pyqtSlot()
    def sendToAll(self):
        data = self.data_input.toPlainText()
        if not data:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập dữ liệu cần gửi")
            return

        self.server.send_to_all(data)
        self.log(f"Đã gửi tới tất cả: {data}", "INFO")

    @pyqtSlot()
    def sendToClient(self):
        button = self.sender()
        if not button:
            return

        host = button.property("host")
        address = button.property("address")

        if not host or not address:
            return

        data = self.data_input.toPlainText()
        if not data:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập dữ liệu cần gửi")
            return

        client_info = (host, int(address))
        self.server.send_to_client(client_info, data)
        self.log(f"Đã gửi tới {host}:{address}: {data}", "INFO")

    def showClientContextMenu(self, position):
        # Kiểm tra nếu có client được chọn
        indexes = self.client_table.selectedIndexes()
        if not indexes:
            return

        # Lấy thông tin client được chọn
        row = indexes[0].row()
        host = self.client_table.item(row, 0).text()
        address = self.client_table.item(row, 1).text()
        client_info = (host, int(address))

        # Tạo menu ngữ cảnh
        menu = QMenu()

        # Thêm các hành động
        if self.server.is_locked and self.server.locked_client == client_info:
            unlock_action = QAction("Mở khóa", self)
            unlock_action.triggered.connect(self.unlockServer)
            menu.addAction(unlock_action)
        else:
            lock_action = QAction("Khóa tới client này", self)
            lock_action.triggered.connect(
                lambda: self.lockToClientFromContext(client_info)
            )
            menu.addAction(lock_action)

        send_action = QAction("Gửi dữ liệu", self)
        send_action.triggered.connect(lambda: self.sendToClientFromContext(client_info))
        menu.addAction(send_action)

        # Hiển thị menu
        menu.exec_(self.client_table.viewport().mapToGlobal(position))

    def lockToClientFromContext(self, client_info):
        # Xác nhận khóa
        reply = QMessageBox.question(
            self,
            "Xác nhận khóa",
            f"Bạn có chắc chắn muốn khóa server với client {client_info[0]}:{client_info[1]}?\n\n"
            "Tất cả các client khác sẽ bị ngắt kết nối và không thể có client mới kết nối.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.server.lock_to_client(client_info)

    def sendToClientFromContext(self, client_info):
        data = self.data_input.toPlainText()
        if not data:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập dữ liệu cần gửi")
            return

        self.server.send_to_client(client_info, data)
        self.log(f"Đã gửi tới {client_info[0]}:{client_info[1]}: {data}", "INFO")

    def log(self, message, level="INFO"):
        # Hiển thị log lên giao diện
        color = "black"
        if level == "ERROR":
            color = "red"
        elif level == "WARNING":
            color = "orange"
        elif level == "INFO":
            color = "blue"

        self.log_display.append(
            f"<span style='color:{color};'>[{level}] {message}</span>"
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServerGUI()
    window.show()
    sys.exit(app.exec_())
