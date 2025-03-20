import os
import datetime
import logging
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtGui import QColor

from logger import Logger  # Import logger tuỳ chỉnh từ logger.py


class LogSignals(QObject):
    """
    Class định nghĩa các signal cho logger.
    """

    textSignal = pyqtSignal(str, str)  # Signal với tham số: text, level


class QListWidgetLogger(logging.Handler):
    """
    Custom logging handler để hiển thị log trong QListWidget của PyQt5.
    """

    def __init__(self, widget):
        super().__init__()
        self.widget = widget  # QListWidget nơi log sẽ hiển thị
        self.setFormatter(
            logging.Formatter("%(asctime)s - [%(levelname)s] : %(message)s")
        )

        # Tạo signals
        self.signals = LogSignals()

        # Kết nối signal với slot để thêm text
        self.signals.textSignal.connect(self.add_text)

    def emit(self, record):
        """Gửi log đến QListWidget."""
        msg = self.format(record)
        list_item = QListWidgetItem(msg)

        # Thay đổi màu sắc theo level
        if record.levelno == logging.DEBUG:
            list_item.setForeground(QColor("blue"))
        elif record.levelno == logging.INFO:
            list_item.setForeground(QColor("green"))
        elif record.levelno == logging.WARNING:
            list_item.setForeground(QColor("orange"))
        elif record.levelno == logging.ERROR:
            list_item.setForeground(QColor("red"))
        elif record.levelno == logging.CRITICAL:
            list_item.setForeground(QColor("darkred"))

        self.widget.addItem(list_item)
        self.widget.scrollToBottom()  # Tự động cuộn xuống log mới nhất

    def add_text(self, text, level=None):
        """
        Thêm text đến QListWidget với màu tùy chỉnh.

        Args:
            text (str): Text cần thêm

        """
        # Tạo timestamp giống định dạng log
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]

        # Tạo text với định dạng giống log
        formatted_text = f"{now} - [{level}] : {text}"

        list_item = QListWidgetItem(formatted_text)

        # Thiết lập màu sắc dựa trên level
        if level == "DEBUG":
            list_item.setForeground(QColor("blue"))
        elif level == "INFO":
            list_item.setForeground(QColor("green"))
        elif level == "WARNING":
            list_item.setForeground(QColor("orange"))
        elif level == "ERROR":
            list_item.setForeground(QColor("red"))
        elif level == "CRITICAL":
            list_item.setForeground(QColor("darkred"))
        else:
            # Tạo text với định dạng giống log
            formatted_text = f"{now} - [DEFAULT] : {text}"

            list_item = QListWidgetItem(formatted_text)

        self.widget.addItem(list_item)
        self.widget.scrollToBottom()


# Hàm thiết lập logger cho giao diện PyQt5
def setup_logger(list_widget, name="LogModel", log_file="logs\\logfile.log"):
    """
    Thiết lập logger để hiển thị log trong QListWidget.

    Args:
        list_widget (QListWidget): Widget hiển thị log.
        name (str): Tên của logger.
        log_file (str): File lưu log.

    Returns:
        tuple: (logger, log_signals) - logger và signals để thêm text
    """
    logger = Logger(name=name, log_file=log_file)
    qt_handler = QListWidgetLogger(list_widget)
    logger.addHandler(qt_handler)

    # Trả về cả logger và signals
    return logger, qt_handler.signals
