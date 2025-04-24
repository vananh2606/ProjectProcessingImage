from serial import Serial
import threading
import time
from PyQt5.QtCore import pyqtSignal, QObject

class VisionController(QObject):
    dataReceived = pyqtSignal(str)

    def __init__(self, com="COM1", baud=9600, strTrigger="TRIGGER"):
        super().__init__()
        self._port = com
        self._baudrate = baud
        self.comport: Serial = None
        self.running = False
        self.strTrigger = strTrigger

    def is_open(self):
        return self.comport is not None and self.comport.is_open

    def open(self):
        try:
            self.comport = Serial(port=self._port, baudrate=self._baudrate, timeout=1)
            print(f"Vision Controller Connected {self._port}")
            self.running = True
            self.read_thread = threading.Thread(target=self.read_data, daemon=True)
            self.read_thread.start()
            return True
        except Exception as ex:
            print(f"Error opening port: {ex}")
            return False

    def close(self):
        try:
            self.running = False
            if self.comport is not None:
                self.comport.close()
                print("Closed Vision Controller")
            return True
        except Exception as e:
            print(f"Failed to close Vision Controller")
            return False

    def read_data(self):
        while self.running and self.is_open():
            try:
                if self.comport.in_waiting > 0:
                    data = self.comport.readline().decode('utf-8').strip()
                    print(data)
                    self.dataReceived.emit(data)
                else:
                    time.sleep(0.05)
            except Exception as ex:
                print(f"Error reading from port: {ex}")
                time.sleep(1)
                break

    def send_trigger(self):
        if self.is_open():
            try:
                self.comport.write((self.strTrigger).encode('utf-8'))
                print(f"Sent: {self.strTrigger}")
            except Exception as ex:
                print(f"Failed to send trigger: {ex}")


def testVisionController():
    visionController = VisionController(com="COM13", baud=9600)
    print(visionController.open())
    visionController.dataReceived.connect(lambda data: print(f">>> Data received: {data}"))
    visionController.send_trigger()
    time.sleep(5)
    visionController.close()

if __name__ == "__main__":
    testVisionController()
