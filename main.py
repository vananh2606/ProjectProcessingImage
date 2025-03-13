import os
import sys
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QTabWidget,
    QFileDialog,
    QPushButton,
    QScrollArea,
)
from PyQt5.QtCore import Qt, QFile, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from functools import partial

from ui.MainWindowUI import Ui_MainWindow

sys.path.append("libs")
from libs.canvas import WindowCanvas, Canvas
from libs.ui_utils import load_style_sheet


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.initUi()

    def initUi(self):
        # Theme
        self.load_theme()

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

        # Canvas
        self.canvas_src = Canvas()
        self.ui.verticalLayoutImageSRC.addWidget(WindowCanvas(self.canvas_src))
        self.canvas_binary = Canvas()
        self.ui.verticalLayoutImageBinary.addWidget(WindowCanvas(self.canvas_binary))
        self.canvas_dst = Canvas()
        self.ui.verticalLayoutImageDST.addWidget(WindowCanvas(self.canvas_dst))
        self.canvas_auto = Canvas()
        self.ui.verticalLayoutScreensAuto.addWidget(WindowCanvas(self.canvas_auto))

        # # ScrollBar
        # scroll_bar = self.add_scrollable_tab(self.ui.tabWidgetModule) # Tạo scroll trong tabWidget
        # self.ui.verticalLayoutModuleTeaching.addWidget(scroll_bar) # Thêm scroll vào layout

    def load_theme(self):
        self.ui.actionLight.triggered.connect(partial(self.set_theme, "light"))
        self.ui.actionDark.triggered.connect(partial(self.set_theme, "dark"))
        self.ui.actionRainbow.triggered.connect(partial(self.set_theme, "rainbow"))

    def set_theme(self, theme: str):
        if theme == "light":
            path = "resources/themes/light_theme.qss"
            load_style_sheet(path, QApplication.instance())
        elif theme == "dark":
            path = "resources/themes/dark_theme.qss"
            load_style_sheet(path, QApplication.instance())
        elif theme == "rainbow":
            path = "resources/themes/rainbow_theme.qss"
            load_style_sheet(path, QApplication.instance())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    load_style_sheet("resources/themes/light_theme.qss", QApplication.instance())
    window.show()
    sys.exit(app.exec_())
