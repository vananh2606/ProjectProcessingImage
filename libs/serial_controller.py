from serial import Serial
import threading
import time

from PyQt5.QtCore import pyqtSignal, QObject

class SerialController(QObject):
    dataReceived = pyqtSignal(str)
    def __init__(self, com="COM1", baud=9600):
        super().__init__()
        self._port = com
        self._baudrate = baud
        self.comport: Serial = None
        self.running = False

    def is_open(self):
        return self.comport is not None and self.comport.is_open
    
    def open(self):
        try:
            self.comport = Serial(port=self._port, baudrate=self._baudrate, timeout=1)
            
            print(f"Serial Controller Connected {self._port}")
            
            self.running = True
            self.read_thread = threading.Thread(target=self.read_data, daemon=True)
            self.read_thread.start()

            return True
        except Exception as ex:
            print(f"Error opening port: {ex}")
            return False
        
    def close(self):
        try:
            if self.comport is not None:
                self.comport.close()
                print("Closed Serial Controller")
            return True
        except Exception as e:
            print(f"Failed to close Serial Controller")
            return False
        
    def read_data(self):
        while self.running and self.is_open():
            try:
                if self.comport.in_waiting > 0:
                    data = self.comport.readline().decode('utf-8').strip()
                    # print(data)
                    self.dataReceived.emit(data)
                else:
                    time.sleep(0.05)  # avoid busy loop
            except Exception as ex:
                print(f"Error reading from port: {ex}")
                time.sleep(1)  # Longer delay after error
                break

    def send_data(self, data: str):
        try:
            if self.is_open():
                self.comport.write((data + '\n').encode('utf-8'))
                print(f"Sent: {data + '\n'}")
                return True
            else:
                print("Port is not open.")
                return False
        except Exception as ex:
            print(f"Error sending data: {ex}")
            return False


def testSerialController():
    serialController = SerialController(com="COM16", baud=9600)
    print(serialController.open())
    serialController.send_data("Hello")
    time.sleep(10)

if __name__ == "__main__":
    testSerialController()

