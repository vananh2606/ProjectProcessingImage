from PyQt5.QtWidgets import QDialog, QApplication, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QMovie
import sys
import os

sys.path.append("./ui")
from LoadingWindowUI import Ui_DialogLoading


class LoadingDialog(QDialog):
    """
    Dialog hiển thị màn hình loading với một thanh tiến trình và animation.
    """
    
    # Các signal để thông báo cập nhật tiến trình
    progressChanged = pyqtSignal(int)  # Cập nhật giá trị tiến trình (0-100)
    messageChanged = pyqtSignal(str)   # Cập nhật thông báo
    
    def __init__(self, parent=None):
        super(LoadingDialog, self).__init__(parent)
        # Sử dụng class UI đã được chuyển đổi
        self.ui = Ui_DialogLoading()
        self.ui.setupUi(self)
        
        # Tạo animation loading
        self.movie = QMovie("resources/loading/loading.gif")
        self.ui.labelLoading.setMovie(self.movie)
        self.movie.start()
        
        # Kết nối signals
        self.progressChanged.connect(self.updateProgress)
        self.messageChanged.connect(self.updateMessage)
        
        # Mặc định progress = 0
        self.ui.progressBar.setValue(0)
        
        # Áp dụng style
        self.applyStyleSheet()
    
    def applyStyleSheet(self):
        """Áp dụng style sheet cho dialog."""
        from PyQt5.QtCore import QFile
        
        file = QFile("resources/loading/style.qss")
        file.open(QFile.ReadOnly | QFile.Text)
        stream = file.readAll()
        self.setStyleSheet(stream.data().decode("UTF-8"))
    
    def updateProgress(self, value):
        """Cập nhật giá trị của thanh tiến trình."""
        if 0 <= value <= 100:
            self.ui.progressBar.setValue(value)
    
    def updateMessage(self, message):
        """Cập nhật nội dung thông báo."""
        self.ui.labelMessage.setText(message)
    
    def closeEvent(self, event):
        """Xử lý khi dialog bị đóng."""
        self.movie.stop()
        event.accept()
        
    def showEvent(self, event):
        """Xử lý khi dialog được hiển thị."""
        # Bắt đầu animation khi hiển thị
        self.movie.start()
        super().showEvent(event)
        
    def hideEvent(self, event):
        """Xử lý khi dialog bị ẩn."""
        # Tạm dừng animation khi ẩn để tiết kiệm tài nguyên
        self.movie.stop()
        super().hideEvent(event)


# Mã kiểm thử nếu chạy trực tiếp file này
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    dialog = LoadingDialog()
    dialog.show()
    
    # Thử nghiệm cập nhật tiến trình
    progress = 0
    
    def updateProgress():
        global progress
        progress += 5
        if progress > 100:
            progress = 0
        dialog.progressChanged.emit(progress)
        dialog.messageChanged.emit(f"Đang xử lý... {progress}%")
    
    timer = QTimer()
    timer.timeout.connect(updateProgress)
    timer.start(100)  # Cập nhật mỗi 200ms
    
    sys.exit(app.exec_())