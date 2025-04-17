import cv2 as cv
from enum import Enum

class ThresholdType(Enum):
    BINARY = (cv.THRESH_BINARY, "Thresh Binary")
    BINARY_INV = (cv.THRESH_BINARY_INV, "Thresh Binary Inverted")
    TRUNC = (cv.THRESH_TRUNC, "Thresh Truncate")
    TOZERO = (cv.THRESH_TOZERO, "Thresh To Zero")
    TOZERO_INV = (cv.THRESH_TOZERO_INV, "Thresh To Zero Inverted")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label

    @classmethod
    def from_label(cls, label: str):
        for item in cls:
            if item.label == label:
                return item
        raise ValueError(f"Không tìm thấy kiểu threshold từ label: {label}")

    @classmethod
    def from_value(cls, value: int):
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"Không tìm thấy kiểu threshold từ giá trị: {value}")

    @classmethod
    def list_labels(cls):
        return [item.label for item in cls]


# ✅ Lấy danh sách hiển thị cho GUI
list_threshold = ThresholdType.list_labels()
print("Danh sách cho GUI:", list_threshold)

# ✅ Từ chuỗi chọn được → lấy giá trị OpenCV
selected_label = "Thresh To Zero"
selected_type = ThresholdType.from_label(selected_label)
print(f"{selected_label} → OpenCV value: {selected_type.value}")

# ✅ Từ value OpenCV → label hiển thị
value = cv.THRESH_TOZERO_INV
label = ThresholdType.from_value(value).label
print(f"Giá trị {value} → label: {label}")