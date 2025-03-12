import sys
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QTabWidget,
    QFileDialog,
    QPushButton,
)
from PyQt5.QtCore import Qt, QFile, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from functools import partial

from ui.MainWindowUI import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.config_ui()
        self.load_theme() 

    def config_ui(self):
        # Dock
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)
        
        # Button
        self.ui.btn_start.setProperty("class", "success")
        self.ui.btn_stop.setProperty("class", "danger")
        self.ui.btn_reset.setProperty("class", "primary")
        self.ui.btn_add.setProperty("class", "primary")
        self.ui.btn_delete.setProperty("class", "danger")
        self.ui.btn_save.setProperty("class", "success")
        self.ui.btn_open_camera.setProperty("class", "success")    
        self.ui.btn_start_camera.setProperty("class", "success")
        self.ui.btn_test_camera.setProperty("class", "primary")
        self.ui.btn_load_image.setProperty("class", "default")
        self.ui.btn_open_folder.setProperty("class", "default")
        self.ui.btn_capture.setProperty("class", "default")
        self.ui.btn_refesh.setProperty("class", "default")
        self.ui.btn_start_teaching.setProperty("class", "success")
        self.ui.btn_open_light.setProperty("class", "success")
        self.ui.btn_connect_server.setProperty("class", "success")

    def load_theme(self):
        self.apply_theme("resources/themes/light_theme.qss")
        self.ui.actionLight.triggered.connect(
            partial(self.apply_theme, "resources/themes/light_theme.qss")
        )
        self.ui.actionDark.triggered.connect(
            partial(self.apply_theme, "resources/themes/dark_theme.qss")
        )
        self.ui.actionRainbow.triggered.connect(
            partial(self.apply_theme, "resources/themes/rainbow_theme.qss")
        )

    def apply_theme(self, path):
        file = QFile(path)
        file.open(QFile.ReadOnly | QFile.Text)
        stream = file.readAll()
        app.setStyleSheet(stream.data().decode("UTF-8"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
