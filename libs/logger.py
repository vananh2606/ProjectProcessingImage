import os
import sys
import csv
import logging
import logging.handlers
from datetime import datetime
from colorama import init, Fore, Style
from termcolor import colored

# Khởi tạo colorama
init()


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter để hiển thị màu sắc trong terminal
    """

    COLORS = {
        "black": Fore.BLACK,
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "blue": Fore.BLUE,
        "magenta": Fore.MAGENTA,
        "cyan": Fore.CYAN,
        "white": Fore.WHITE,
        "reset": Fore.RESET,
    }

    ATTRIBUTES = {
        "reset": "reset",
        "bold": "bold",
        "dark": "dark",
        "underline": "underline",
        "blink": "blink",
        "reverse": "reverse",
        "concealed": "concealed",
    }

    log_format = "%(asctime)s - [%(name)s] - [%(levelname)s] - [in %(pathname)s:%(lineno)d] : %(message)s"

    FORMATS = {
        logging.DEBUG: colored(log_format, "cyan"),
        logging.INFO: colored(log_format, "green"),
        logging.WARNING: colored(log_format, "yellow"),
        logging.ERROR: colored(log_format, "red", attrs=["bold", "blink"]),
        logging.CRITICAL: colored(
            log_format, "red", on_color="on_red", attrs=["bold", "blink"]
        ),
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        msg = formatter.format(record)
        return msg


class Logger(logging.Logger):
    """
    Logger class kế thừa từ logging.Logger
    Hỗ trợ lưu log vào file với nhiều định dạng và hiển thị màu sắc trên terminal
    """

    def __init__(
        self,
        name,
        log_file="logs\logfile.log",
        level=logging.DEBUG,
        enable_console=True,
        enable_file=True,
        maxBytes=1024 * 1024 * 10,  # 10MB
        backupCount=10,
    ):
        """
        Khởi tạo Logger

        Args:
            name (str): Tên của logger
            file_name (str): Tên file log
            log_dir (str): Thư mục lưu file log
            level (int): Mức độ log (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            enable_console (bool): Bật/tắt log trên console
            enable_file (bool): Bật/tắt log vào file
            maxBytes (int): Kích thước tối đa của file log trước khi xoay vòng (bytes)
            backupCount (int): Số lượng file backup tối đa
        """
        # Gọi constructor của lớp cha (logging.Logger)
        super(Logger, self).__init__(name)

        self.propagate = False
        self.log_file = log_file
        self.maxBytes = maxBytes
        self.backupCount = backupCount

        # Format string cho log
        self.log_format = "%(asctime)s - [%(name)s] - [%(levelname)s] - [in %(pathname)s:%(lineno)d] : %(message)s"

        # Thêm console handler nếu được yêu cầu
        if enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_formatter = ColoredFormatter(self.log_format)
            console_handler.setFormatter(console_formatter)
            self.addHandler(console_handler)

        # Thêm file handlers nếu được yêu cầu
        log_file_date = log_file + "_" + datetime.now().strftime("%Y_%m_%d") + ".log"
        if enable_file:
            formatter = logging.Formatter(self.log_format)
            file_handler = logging.handlers.RotatingFileHandler(
                log_file_date,
                maxBytes=self.maxBytes,
                backupCount=self.backupCount,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            self.addHandler(file_handler)

    def convert_log2txt(self, log_path, txt_path, encoding="utf-8"):
        """
        Chuyển log file sang file txt

        Args:
            log_path (str): Tên file log
            txt_path (str): Tên file txt
            encoding (str): Mã hoá
        """
        if not os.path.exists(txt_path):
            os.mkdir(txt_path)
        with open(log_path, encoding=encoding) as log_file:
            with open(txt_path, "w", encoding=encoding) as txt_file:
                txt_file.write(log_file.read())

    def convert_log2csv(self, log_path, csv_path, encoding="utf-8"):
        """
        Chuyển log file sang file csv

        Args:
            log_path (str): Tên file log
            csv_path (str): Tên file csv
            encoding (str): Mã hoá
        """
        if not os.path.exists(csv_path):
            os.mkdir(csv_path)
        with open(log_path, encoding=encoding) as log_file:
            with open(csv_path, "w", encoding=encoding) as csv_file:
                csv_writer = csv.writer(csv_file)
                for line in log_file:
                    csv_writer.writerow(line.strip().split(" - "))

    def exception(self, msg, *args, exc_info=True, include_traceback=False, **kwargs):
        """
        Log một exception với tùy chọn bỏ qua traceback

        Args:
            msg (str): Thông điệp lỗi
            exc_info (bool/Exception): Thông tin exception
            include_traceback (bool): Có bao gồm traceback hay không
            *args: Các tham số bổ sung cho msg
            **kwargs: Các tham số bổ sung
        """
        if not include_traceback:
            # Nếu không bao gồm traceback, ghi log error với exception nhưng không có stack trace
            if exc_info:
                import sys

                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_value:
                    msg = f"{msg}: {exc_value}"
            self.error(msg, *args, **kwargs)
        else:
            # Nếu bao gồm traceback, gọi phương thức exception gốc
            super().exception(msg, *args, **kwargs)


def test_write_log():
    # Ví dụ sử dụng
    logger = Logger(name="test_logger", log_file="logs/test")
    logger.debug("Đây là thông báo DEBUG")
    logger.info("Đây là thông báo INFO")
    logger.warning("Đây là thông báo WARNING")
    logger.error("Đây là thông báo ERROR")
    logger.critical("Đây là thông báo CRITICAL")

    try:
        x = 1 / 0
    except Exception:
        logger.exception("Có lỗi xảy ra")


if __name__ == "__main__":
    test_write_log()
