from PyQt5.QtCore import QThread, pyqtSignal
import cv2 as cv
import time

from cameras.hik import HIK
from cameras.soda import SODA
from cameras.webcam import Webcam
from cameras.base_camera import NO_ERROR


class CameraThread(QThread):
    frameCaptured = pyqtSignal(object)

    def __init__(self, camera, config: dict, parent=None):
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

                time.sleep(0.04)

    def stop_camera(self):
        self.running = False

    def close_camera(self):
        self.stop_camera()
        self.camera.stop_grabbing()
        self.camera.close()
