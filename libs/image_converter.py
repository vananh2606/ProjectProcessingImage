import cv2 as cv
import numpy as np
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt


class ImageConverter:
    def __init__(self, image_path):
        self.image_path = image_path

    @staticmethod
    def opencv_to_qimage(cv_image):
        # Chuyển BGR sang RGB
        rgb_image = cv.cvtColor(cv_image, cv.COLOR_BGR2RGB)

        # Lấy thông số
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        # Tạo QImage
        return QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)

    @staticmethod
    def opencv_to_qpixmap(cv_image, scale_to_size=None):
        # Chuyển OpenCV sang QImage
        qimage = ImageConverter.opencv_to_qimage(cv_image)

        # Tạo QPixmap
        qpixmap = QPixmap.fromImage(qimage)

        # Scale QPixmap
        if scale_to_size:
            qpixmap = qpixmap.scaled(
                scale_to_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        return qpixmap

    @staticmethod
    def smooth_label(label, image):
        # Convert OpenCV image to QPixmap
        qpixmap = ImageConverter.opencv_to_qpixmap(image, label.size())

        # Calculate position to center the image
        x = (label.size().width() - qpixmap.width()) // 2
        y = (label.size().height() - qpixmap.height()) // 2

        # Set Label
        label.clear()
        label.setPixmap(qpixmap)
        label.setContentsMargins(x, y, x, y)