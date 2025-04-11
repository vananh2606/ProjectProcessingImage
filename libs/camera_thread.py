from PyQt5.QtCore import QThread, pyqtSignal
import cv2 as cv
import time
import sys 

sys.path.append("cameras")

from hik import HIK
from soda import SODA
from webcam import Webcam
from base_camera import NO_ERROR


class CameraThread(QThread):
    frameCaptured = pyqtSignal(object)

    def __init__(self, camera, config: dict = {"id": "0", "feature": ""}, parent=None):
        super().__init__(parent)

        if camera == "HIK":
            self.camera = HIK(config)
        elif camera == "SODA":
            self.camera = SODA(config)
        elif camera == "Webcam":
            self.camera = Webcam(config)
        self.b_open = None
        self.frame = None
        self.running = False

    def open_camera(self):
        self.b_open = self.camera.open()
        self.b_open &= self.camera.start_grabbing()

    def grab_camera(self):
        if self.b_open:
            err, self.frame = self.camera.grab()
            return self.frame
        else:
            return None

    def run(self):
        if self.b_open:
            self.running = True
            while self.running:
                err, self.frame = self.camera.grab()

                if err != NO_ERROR:
                    print("Camera error: ", err)
                    break
                else:
                    self.frameCaptured.emit(self.frame)

                self.msleep(50)

    def stop_camera(self):
        self.running = False
        self.msleep(50)

    def close_camera(self):
        self.stop_camera()
        if hasattr(self, 'camera') and self.camera:
            self.camera.stop_grabbing()
            self.camera.close()
        self.wait()

    # def __init__(self, parent=None):
    #     super().__init__(parent)
    #     self.camera = cv.VideoCapture()
    #     self.b_open = None
    #     self.frame = None
    #     self.running = False

    # def open_camera(self):
    #     self.b_open = self.camera.open()
    #     # self.b_open &= self.camera.start_grabbing()

    # def grab_camera(self):
    #     if self.b_open:
    #         err, self.frame = self.camera.read()
    #         return self.frame
    #     else:
    #         return None

    # def run(self):
    #     if self.b_open:
    #         self.running = True
    #         while self.running:
    #             err, self.frame = self.camera.read()

    #             if err:
    #                 self.frameCaptured.emit(self.frame, time.time())

    #             time.sleep(0.04)

    # def stop_camera(self):
    #     print("Stop Camera")
    #     self.running = False

    # def close_camera(self):
    #     self.stop_camera()
    #     self.camera.release()
