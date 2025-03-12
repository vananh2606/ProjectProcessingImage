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

from gui.MainWindowUI import Ui_MainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        self.load_theme("res/theme/dark_theme.qss")
        self.ui.actionLight.triggered.connect(
            partial(self.load_theme, "res/theme/light_theme.qss")
        )
        self.ui.actionDark.triggered.connect(
            partial(self.load_theme, "res/theme/dark_theme.qss")
        )

        self.ui.btn_start.setProperty("class", "success")

    def load_theme(self, path):
        file = QFile(path)
        file.open(QFile.ReadOnly | QFile.Text)
        stream = file.readAll()
        app.setStyleSheet(stream.data().decode("UTF-8"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
