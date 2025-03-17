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

    @staticmethod
    def draw_classification_result(image, result, font_scale=0.8, thickness=2):
        """
        Vẽ kết quả phân loại lên ảnh

        Args:
            image: Ảnh OpenCV (numpy array)
            result: Dict chứa kết quả phân loại
            font_scale: Kích thước font
            thickness: Độ dày của văn bản

        Returns:
            Ảnh đã vẽ thông tin phân loại
        """
        if image is None or result is None:
            return image

        # Tạo bản sao của ảnh để không ảnh hưởng đến ảnh gốc
        img_with_result = image.copy()

        # Lấy thông tin từ kết quả
        class_name = result.get("class_name", "Unknown")
        confidence = result.get("confidence", 0.0)
        inference_time = result.get("inference_time", 0.0)
        model_name = result.get("model_name", "")

        # Chuẩn bị văn bản để hiển thị
        label = f"{class_name}: {confidence:.2f}"
        time_text = f"Time: {inference_time*1000:.1f}ms"
        model_text = f"Model: {model_name}" if model_name else ""

        # Vẽ hình chữ nhật màu đen mờ ở dưới cùng để hiển thị thông tin
        height, width = img_with_result.shape[:2]
        # Tăng độ cao của hình chữ nhật nếu có tên model
        rect_height = 90 if model_name else 70
        cv.rectangle(
            img_with_result, (0, height - rect_height), (width, height), (0, 0, 0), -1
        )

        # Vẽ tên lớp và độ tin cậy
        cv.putText(
            img_with_result,
            label,
            (10, height - rect_height + 30),
            cv.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness,
        )

        # Vẽ thời gian xử lý
        cv.putText(
            img_with_result,
            time_text,
            (10, height - rect_height + 60),
            cv.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness,
        )

        # Vẽ tên model nếu có
        if model_name:
            cv.putText(
                img_with_result,
                model_text,
                (10, height - rect_height + 90),
                cv.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                thickness,
            )

        return img_with_result
