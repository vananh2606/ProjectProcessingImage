from PyQt5.QtWidgets import QWidget, QApplication, QDialog
from PyQt5.QtCore import *
from PyQt5.QtGui import *

import os
import sys
import serial
import serial.tools
import serial.tools.list_ports
sys.path.append("./ui")
sys.path.append("libs")
sys.path.append("./")

from AutoScannerUI import Ui_AutoScanner
from serial_controller import SerialController
from logger import Logger
from canvas import WindowCanvas, Canvas
from shape import Shape
from ui_utils import load_style_sheet, update_style, add_scroll, ndarray2pixmap

class AutoScannerDlg(QDialog):
    scannerResult = pyqtSignal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_AutoScanner()
        self.ui.setupUi(self)
        self.scanner_controller = None

        self.project_name = "Project Name"
        self.log_path = "logs\\logfile.log"
        self.ui_logger = Logger(name=self.project_name, log_file=self.log_path)

        self.initUI()
        self.connectUI()
        self.apply_default_config()

    def initUI(self):
        self.ui.btn_open_scanner.setProperty("class", "success")
        self.ui.btn_cancel.setProperty("class", "danger")
        self.ui.btn_apply.setProperty("class", "primary")
    
    def connectUI(self):
        self.ui.btn_open_scanner.clicked.connect(self.on_click_open_scanner)
        self.ui.btn_apply.clicked.connect(self.on_click_apply)
        self.ui.btn_cancel.clicked.connect(self.on_click_cancel)

    def apply_default_config(self):
        try:
            default_config = {
                "scanner":{
                    "comport_scanner": "COM11",
                    "baudrate_scanner": '9600',
                },
            }
            

            # Áp dụng cấu hình mặc định
            self.set_config(default_config)
            self.ui_logger.info("Đã áp dụng cấu hình mặc định")

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi áp dụng cấu hình mặc định: {str(e)}")

    def set_config(self, config):
        if "scanner" in config:
            scanner_config = config["scanner"]
            comports, baudrates = self.find_comports_and_baurates()
            self.ui.combo_comport_scanner.setEditable(True)
            self.ui.combo_baudrate_scanner.setEditable(True)
            self.add_combox_item(self.ui.combo_comport_scanner, comports)
            self.add_combox_item(self.ui.combo_baudrate_scanner, baudrates)
            self.set_combobox_text(
                self.ui.combo_comport_scanner, scanner_config.get("comport_scanner", "COM11")
            )
            self.set_combobox_text(
                self.ui.combo_baudrate_scanner, scanner_config.get("baudrate_scanner", "9600")
            )

    def init_scanner(self, com_port, baud_rate):
        try:
            # Ghi log thông số io
            self.ui_logger.info(
                f"Khởi tạo Scanner: COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            self.scanner_controller = SerialController(com=com_port, baud=baud_rate)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo Scanner: {str(e)}")
            return False

    def set_combobox_text(self, combobox, text):
        """
        Hàm phụ trợ để đặt giá trị văn bản cho combobox.

        Args:
            combobox (QComboBox): Combobox cần đặt giá trị
            text (str): Giá trị văn bản cần đặt
        """
        index = combobox.findText(text)
        if index >= 0:
            combobox.setCurrentIndex(index)

    def add_combox_item(self, combobox, items: list):
        combobox.clear()
        for item in items:
            combobox.addItem(item)

    def find_comports_and_baurates(self):
        comports = serial.tools.list_ports.comports()
        comports = [port for port, _, _ in comports]

        baudrates = list(map(str, serial.Serial.BAUDRATES))

        return comports, baudrates
    
    def on_click_open_scanner(self):
        if self.ui.btn_open_scanner.text() == "Open":
            self.open_scanner()
        else:
            self.close_scanner()

    def open_scanner(self):
        try:
            # Lấy thông số từ giao diện
            comport_scanner = self.ui.combo_comport_scanner.currentText()
            baudrate_scanner = int(self.ui.combo_baudrate_scanner.currentText())
            self.init_scanner(comport_scanner, baudrate_scanner)

            # Mở kết nối với bộ điều khiển
            status = self.scanner_controller.open()

            self.scanner_controller.dataReceived.connect(self.handle_message_scanner)

            self.ui.btn_open_scanner.setText("Close")
            self.ui.btn_open_scanner.setProperty("class", "danger")
            update_style(self.ui.btn_open_scanner)

            if status:
                self.ui_logger.info("Scanner controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to Scanner controller")

        except Exception as e:
            self.ui_logger.error(f"Error Open Scanner: {e}")

    def close_scanner(self):
        try:
            # Đóng kết nối với bộ điều khiển
            status = self.scanner_controller.close()

            self.ui.btn_open_scanner.setText("Open")
            self.ui.btn_open_scanner.setProperty("class", "success")
            update_style(self.ui.btn_open_scanner)

            self.ui.line_message_scanner.setText("")

            if status:
                self.ui_logger.info("Scanner controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from Scanner controller")
        except Exception as e:
            self.ui_logger.error(f"Error Close Scanner: {e}")

    def handle_message_scanner(self, data: str):
        try:
            self.ui.line_message_scanner.setText(data)
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value scanner: {e}")

    def on_click_apply(self):
        """
        Phát tín hiệu kết quả quét và đóng dialog.
        """
        # Phát tín hiệu với kết quả quét
        scanned_model = self.ui.line_message_scanner.text()
        if scanned_model:
            self.scannerResult.emit(scanned_model)
        
        if self.scanner_controller is not None:
            self.scanner_controller.close()
            self.scanner_controller = None

        self.accept()

    def on_click_cancel(self):
        if self.scanner_controller is not None:
            self.scanner_controller.close()
            self.scanner_controller = None

        self.reject()

    def closeEvent(self, event):
        """
        Đóng kết nối scanner khi đóng dialog.
        """
        if self.scanner_controller is not None:
            self.scanner_controller.close()
            self.scanner_controller = None
        
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AutoScannerDlg()
    win.show()
    sys.exit(app.exec_())