# from utils import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

from serial import Serial
import time


class DCPController:
    def __init__(self, com="COM1", baud=19200):
        super().__init__()
        self._port = com
        self._baudrate = baud
        self.comport: Serial = None

    def is_open(self):
        return self.comport is not None and self.comport.is_open

    def set_light_value(self, channel=0, val=10):
        channel_str = {0: "SA", 1: "SB", 2: "SC", 3: "SD"}.get(channel, "")
        value_str = str(val).zfill(3)
        data = f"{channel_str}0{value_str}#"
        self.send_data(data)

    def on_channel(self, channel=0, val=10):
        self.set_light_value(channel, val)

    def off_channel(self, channel=0):
        self.set_light_value(channel, 0)

    def send_data(self, data):
        if self.is_open():
            self.comport.write(data.encode())

    def off_all_channels(self):
        for i in range(4):
            self.off_channel(i)

    def open(self):
        self.close()
        time.sleep(0.1)
        try:
            self.comport = Serial(port=self._port, baudrate=self._baudrate)
            return self.comport.is_open
        except:
            self.comport = None
            return False

    def close(self):
        try:
            if self.comport is not None:
                self.off_all_channels()
                self.comport.close()
            return True
        except:
            return False


class LCPController:
    def __init__(self, com="COM1", baud=9600):
        super().__init__()
        self._port = com
        self._baudrate = baud
        self.comport: Serial = None

    def is_open(self):
        return self.comport is not None and self.comport.is_open

    def set_light_value(self, channel=0, val=100):
        data = "\x02%sw%.4d\x03" % (channel, val)
        self.send_data(data)

    def on_channel(self, channel=0):
        data = "\x02%so\x03" % (channel)
        self.send_data(data)

    def off_channel(self, channel=0):
        data = "\x02%sf\x03" % (channel)
        self.send_data(data)

    def send_data(self, data):
        if self.is_open():
            self.comport.write(data.encode())

    def off_all_channels(self):
        for i in range(4):
            self.off_channel(i)

    def open(self):
        self.close()
        time.sleep(0.1)

        try:
            self.comport = Serial(port=self._port, baudrate=self._baudrate)
            return self.comport.is_open
        except:
            self.comport = None
            return False

    def close(self):
        try:
            if self.comport is not None:
                self.off_all_channels()
                self.comport.close()
            return True
        except:
            return False


def test_DCPController():
    dcp = DCPController(com="COM14")
    print(dcp.open())
    dcp.on_channel(0, 10)
    # dcp.set_light_value(0, 10)
    time.sleep(3)
    dcp.off_channel(0)
    dcp.close()


def test_LCPController():
    lcp = LCPController(com="COM14")
    print(lcp.open())
    lcp.on_channel(0)
    lcp.set_light_value(0, 100)
    time.sleep(3)
    lcp.off_channel(0)
    lcp.close()


if __name__ == "__main__":
    test_DCPController()
    # test_LCPController()
