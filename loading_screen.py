from PyQt5.QtWidgets import QMainWindow, QApplication, QPushButton, QVBoxLayout, QWidget, QMessageBox
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import sys
import time
import threading

from libs.loading import LoadingDialog

class MainWindow(QMainWindow):
    # Định nghĩa signals
    signalShowLoading = pyqtSignal(str)  # Signal để hiển thị loading dialog với thông báo
    signalHideLoading = pyqtSignal()     # Signal để ẩn loading dialog
    signalUpdateProgress = pyqtSignal(int)  # Signal để cập nhật tiến trình
    
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Demo LoadingDialog")
        self.resize(500, 400)
        
        # Khởi tạo UI
        self.initUI()
        
        # Khởi tạo loading dialog
        self.loading_dialog = LoadingDialog(self)
        
        # Kết nối signals
        self.signalShowLoading.connect(self.showLoading)
        self.signalHideLoading.connect(self.hideLoading)
        self.signalUpdateProgress.connect(self.updateLoadingProgress)
    
    def initUI(self):
        # Widget chính
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout(central_widget)
        
        # Các nút thử nghiệm
        btn_simple = QPushButton("Loading đơn giản (2 giây)")
        btn_simple.clicked.connect(self.testSimpleLoading)
        
        btn_progress = QPushButton("Loading với tiến trình")
        btn_progress.clicked.connect(self.testProgressLoading)
        
        btn_thread = QPushButton("Loading với xử lý nặng (thread)")
        btn_thread.clicked.connect(self.testThreadLoading)
        
        # Thêm các nút vào layout
        layout.addWidget(btn_simple)
        layout.addWidget(btn_progress)
        layout.addWidget(btn_thread)
        layout.addStretch()
    
    def showLoading(self, message="Đang tải..."):
        """Hiển thị dialog loading với thông báo."""
        self.loading_dialog.updateMessage(message)
        self.loading_dialog.show()
    
    def hideLoading(self):
        """Ẩn dialog loading."""
        self.loading_dialog.hide()
    
    def updateLoadingProgress(self, value):
        """Cập nhật giá trị tiến trình cho loading dialog."""
        self.loading_dialog.progressChanged.emit(value)
    
    def testSimpleLoading(self):
        """Test loading đơn giản trong 2 giây."""
        self.signalShowLoading.emit("Vui lòng đợi trong giây lát...")
        
        # Ẩn dialog sau 2 giây
        QTimer.singleShot(2000, self.signalHideLoading.emit)
    
    def testProgressLoading(self):
        """Test loading với thanh tiến trình."""
        self.signalShowLoading.emit("Đang xử lý dữ liệu...")
        
        # Thiết lập tiến trình ban đầu
        self.progress_value = 0
        
        # Tạo timer để mô phỏng tiến trình
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self.simulateProgress)
        self.progress_timer.start(10)  # Cập nhật mỗi 50ms
    
    def simulateProgress(self):
        """Mô phỏng tiến trình xử lý."""
        self.progress_value += 1
        
        if self.progress_value <= 100:
            # Cập nhật tiến trình
            self.signalUpdateProgress.emit(self.progress_value)
            
            # Cập nhật thông báo
            if self.progress_value < 30:
                message = f"Đang khởi tạo... {self.progress_value}%"
            elif self.progress_value < 60:
                message = f"Đang xử lý dữ liệu... {self.progress_value}%"
            elif self.progress_value < 90:
                message = f"Đang kiểm tra kết quả... {self.progress_value}%"
            else:
                message = f"Hoàn thiện... {self.progress_value}%"
            
            self.loading_dialog.messageChanged.emit(message)
        else:
            # Kết thúc tiến trình
            self.progress_timer.stop()
            self.signalHideLoading.emit()
            QMessageBox.information(self, "Thành công", "Đã hoàn thành xử lý!")
    
    def testThreadLoading(self):
        """Test loading với xử lý nặng trong thread riêng."""
        self.signalShowLoading.emit("Đang bắt đầu xử lý...")
        
        # Khởi động thread xử lý
        thread = threading.Thread(target=self.heavyTask)
        thread.daemon = True
        thread.start()
    
    def heavyTask(self):
        """Mô phỏng một tác vụ nặng trong thread."""
        # Hiển thị ban đầu
        self.signalUpdateProgress.emit(0)
        
        # Giả lập xử lý nặng với 10 bước
        steps = 10
        for i in range(1, steps + 1):
            # Giả lập công việc trong mỗi bước
            time.sleep(0.3)
            
            # Cập nhật tiến trình
            percent = int(i * 100 / steps)
            self.signalUpdateProgress.emit(percent)
            
            # Cập nhật thông báo
            self.loading_dialog.messageChanged.emit(f"Đang xử lý công việc nặng ({i}/{steps})...")
        
        # Hoàn thành
        self.signalHideLoading.emit()
        
        # Hiển thị thông báo hoàn thành (đảm bảo gọi từ main thread)
        QTimer.singleShot(0, lambda: QMessageBox.information(
            self, "Hoàn thành", "Đã xử lý xong công việc nặng!"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())