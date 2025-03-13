import logging
from logging import FileHandler, Formatter, StreamHandler
from logging.handlers import RotatingFileHandler

from colorama import init
from termcolor import colored

init()


class CustomFormatter(logging.Formatter):
    fmt = "%(asctime)s - [%(name)s] - [%(levelname)s] - [in %(pathname)s:%(lineno)d] : %(message)s"

    FORMATS = {
        logging.DEBUG: colored(fmt, "white"),
        logging.INFO: colored(fmt, "green"),
        logging.WARNING: colored(fmt, "yellow"),
        logging.ERROR: colored(fmt, "red", attrs=["bold", "blink"]),
        logging.CRITICAL: colored(fmt, "red", "on_red", ["bold", "blink"]),
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


class Logger(logging.Logger):
    def __init__(
        self,
        name="",
        file_name=None,
        maxBytes=10000,
        backupCount=10,
        file_level=logging.DEBUG,
        stream_level=logging.DEBUG,
    ) -> None:
        """
        name: name of logger
        file_name: path of log file, if file_name is None logger don't add file_handler
        file_level: level of file_handler
        stream_level: level of stream_handler(DEBUG -> CRITICAL)
        """
        super(Logger, self).__init__(name)
        # if no logger to console
        self.propagate = False
        # self.disabled = True

        if file_name is not None:
            fmt = "%(asctime)s - [%(name)s] - [%(levelname)s] - [in %(pathname)s:%(lineno)d] : %(message)s"
            formatter = Formatter(fmt)
            file_handler = RotatingFileHandler(
                file_name, maxBytes=maxBytes, backupCount=backupCount
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(formatter)
            self.addHandler(file_handler)

        formatter = CustomFormatter()
        stream_handler = StreamHandler()
        stream_handler.setLevel(stream_level)
        stream_handler.setFormatter(formatter)
        self.addHandler(stream_handler)


def test():
    logger = Logger(
        name="mylog",
        file_name="logfile.log",
        file_level=logging.INFO,
        stream_level=logging.INFO,
    )

    try:
        1 / 0
    except Exception as e:
        logger.error(e)

    logger.info("this is info")
    logger.warning("this is warning")
    logger.error("this is error")
    logger.critical("this is critical")


if __name__ == "__main__":
    test()
