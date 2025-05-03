import sys
from PyQt5.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QPushButton, QLineEdit, QGroupBox, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from libs.serial_controller import SerialController

class ScannerDialog(QDialog):
    """
    Dialog để chọn cổng COM và test Scanner.
    Kết quả quét sẽ được trả về thông qua signal scannerResult.
    """
    scannerResult = pyqtSignal(str)
    
    def __init__(self, comports, baudrates, parent=None):
        super(ScannerDialog, self).__init__(parent)
        self.setWindowTitle("Scanner Configuration")
        self.setMinimumWidth(400)
        self.comports = comports
        self.baudrates = baudrates
        self.scanner = None
        self.scanner_controller = None
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # COM Port Group
        com_group = QGroupBox("Scanner COM Port")
        com_layout = QHBoxLayout()
        
        self.label_com = QLabel("COM Port:")
        self.combo_com = QComboBox()
        self.combo_com.addItems(self.comports)
        
        self.label_baudrate = QLabel("Baudrate:")
        self.combo_baudrate = QComboBox()
        self.combo_baudrate.addItems(self.baudrates)
        
        com_layout.addWidget(self.label_com)
        com_layout.addWidget(self.combo_com)
        com_layout.addWidget(self.label_baudrate)
        com_layout.addWidget(self.combo_baudrate)
        
        com_group.setLayout(com_layout)
        layout.addWidget(com_group)
        
        # Test Scanner Group
        test_group = QGroupBox("Test Scanner")
        test_layout = QVBoxLayout()
        
        self.btn_open_scanner = QPushButton("Open Scanner")
        self.btn_open_scanner.clicked.connect(self.on_open_scanner)
        
        self.label_result = QLabel("Scan Result:")
        self.line_result = QLineEdit()
        self.line_result.setReadOnly(True)
        
        test_layout.addWidget(self.btn_open_scanner)
        test_layout.addWidget(self.label_result)
        test_layout.addWidget(self.line_result)
        
        test_group.setLayout(test_layout)
        layout.addWidget(test_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self.on_apply)
        self.btn_apply.setEnabled(False)  # Không cho phép Apply cho đến khi có kết quả scan
        
        button_layout.addWidget(self.btn_cancel)
        button_layout.addWidget(self.btn_apply)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def on_open_scanner(self):
        """
        Mở kết nối với Scanner và thiết lập kết nối dữ liệu.
        """
        try:
            # Đóng kết nối cũ nếu có
            if self.scanner_controller is not None:
                self.scanner_controller.close()
                self.scanner_controller = None
                
            # Thiết lập text của nút
            if self.btn_open_scanner.text() == "Open Scanner":
                # Lấy thông số COM và baudrate
                com_port = self.combo_com.currentText()
                baudrate = int(self.combo_baudrate.currentText())
                
                # Tạo một instance của SerialController (cần import)
                self.scanner_controller = SerialController(com=com_port, baud=baudrate)
                
                # Mở kết nối
                status = self.scanner_controller.open()
                
                if status:
                    # Kết nối signal từ scanner
                    self.scanner_controller.dataReceived.connect(self.on_data_received)
                    
                    # Cập nhật UI
                    self.btn_open_scanner.setText("Close Scanner")
                    self.btn_open_scanner.setProperty("class", "danger")
                    self.update_style(self.btn_open_scanner)
                    
                    # Thông báo
                    QMessageBox.information(self, "Scanner", "Scanner connected successfully. Please scan a model code.")
                else:
                    QMessageBox.warning(self, "Scanner Error", f"Could not connect to Scanner on {com_port}. Please check the connection.")
            else:
                # Đóng kết nối
                if self.scanner_controller is not None:
                    self.scanner_controller.close()
                    self.scanner_controller = None
                
                # Cập nhật UI
                self.btn_open_scanner.setText("Open Scanner")
                self.btn_open_scanner.setProperty("class", "success")
                self.update_style(self.btn_open_scanner)
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error opening scanner: {str(e)}")
    
    def on_data_received(self, data):
        """
        Xử lý dữ liệu nhận được từ scanner.
        """
        # Hiển thị dữ liệu lên giao diện
        self.line_result.setText(data)
        
        # Bật nút Apply nếu có dữ liệu
        if data:
            self.btn_apply.setEnabled(True)
    
    def on_apply(self):
        """
        Phát tín hiệu kết quả quét và đóng dialog.
        """
        # Phát tín hiệu với kết quả quét
        scanned_model = self.line_result.text().strip()
        if scanned_model:
            self.scannerResult.emit(scanned_model)
        
        # Đóng dialog với kết quả thành công
        self.accept()
    
    def update_style(self, widget):
        """
        Cập nhật style cho widget.
        """
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()
    
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
    window = ScannerDialog(["COM1", "COM2"], ['9600', '115200'])
    window.show()
    sys.exit(app.exec_())