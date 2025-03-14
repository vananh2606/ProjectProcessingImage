import os
import logging
from PyQt5.QtWidgets import QListWidgetItem
from PyQt5.QtGui import QColor
from logger import Logger  # Import logger tuỳ chỉnh từ logger.py


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

    def emit(self, record):
        """Gửi log đến QListWidget."""
        msg = self.format(record)
        list_item = QListWidgetItem(msg)

        # Thay đổi màu sắc theo level
        if record.levelno == logging.NOTSET:
            pass
        elif record.levelno == logging.DEBUG:
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


# Hàm thiết lập logger cho giao diện PyQt5
def setup_logger(list_widget, name="PyQtLogger", log_file="logs\logfile.log"):
    """
    Thiết lập logger để hiển thị log trong QListWidget.
    Args:
        list_widget (QListWidget): Widget hiển thị log.
        log_file (str): File lưu log.
    """

    logger = Logger(name=name, log_file=log_file)
    qt_handler = QListWidgetLogger(list_widget)
    logger.addHandler(qt_handler)
    return logger
