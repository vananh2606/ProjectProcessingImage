from PyQt5.QtWidgets import QWidget, QApplication
# from PyQt5.QtCore import *
# from PyQt5.QtGui import *

import os
import sys
sys.path.append("./ui")
sys.path.append("libs")
sys.path.append("./cameras")


from CameraUI import Ui_FormCamera
from camera_thread import CameraThread
from logger import Logger
from canvas import WindowCanvas, Canvas
from shape import Shape
from ui_utils import load_style_sheet, update_style, add_scroll, ndarray2pixmap
from cameras import HIK, SODA, Webcam, get_camera_devices


class CameraDlg(QWidget):
    def __init__(self, canvas_screen: Canvas, parent=None):
        super().__init__(parent)
        self.ui = Ui_FormCamera()
        self.ui.setupUi(self)
        self.canvas_screen = canvas_screen
        self.camera_thread = None
        self.current_image = None

        self.project_name = "Project Name"
        self.log_path = "logs\\logfile.log"
        self.ui_logger = Logger(name=self.project_name, log_file=self.log_path)

        self.initUI()
        self.connectUI()
        self.apply_default_config()

    def initUI(self):
        self.ui.btn_open_camera.setProperty("class", "success")
        self.ui.btn_start_camera.setProperty("class", "success")
        self.ui.btn_test_camera.setProperty("class", "primary")

    def connectUI(self):
        self.ui.btn_open_camera.clicked.connect(self.on_click_open_camera)
        self.ui.btn_start_camera.clicked.connect(self.on_click_start_camera)
        self.ui.btn_test_camera.clicked.connect(self.on_click_test_camera)

        self.ui.combo_type_camera.currentIndexChanged.connect(
            self.on_change_camera_type
        )

    def apply_default_config(self):
        """
        Áp dụng cấu hình mặc định cho ứng dụng.
        Được gọi khi không có model nào được tìm thấy hoặc có lỗi khi tải model.
        """
        try:
            default_config = {
                "device":{
                    "type":"Webcam",
                    "id":"0",
                    "feature":""
                },
                "lighting":{	
                    "channels": [10, 10, 10, 10]
                }
            }

            # Áp dụng cấu hình mặc định
            self.set_config(default_config)
            self.ui_logger.info("Đã áp dụng cấu hình mặc định")

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi áp dụng cấu hình mặc định: {str(e)}")

    def get_config(self) -> dict:
        # Khởi tạo từ điển cấu hình
        camera_config = { 
            "device":{
                "type": self.ui.combo_type_camera.currentText(),
                "id": self.ui.combo_id_camera.currentText(),
                "feature": self.ui.combo_feature.currentText()
            },
            "lighting":{
                "channels": [
                    self.ui.spin_channel_0.value(),
                    self.ui.spin_channel_1.value(),
                    self.ui.spin_channel_2.value(),
                    self.ui.spin_channel_3.value()
                ],
            }
        }
        print(camera_config)

        return camera_config

    def set_config(self, config):
        # Áp dụng cấu hình camera
        if "device" in config:
            camera_config = config["device"]
            self.add_combox_item(
                self.ui.combo_type_camera, ["Webcam", "HIK", "SODA"]
            )
            self.set_combobox_text(
                self.ui.combo_type_camera, camera_config.get("type", "Webcam")
            )
            id_camera, features = self.find_camera_devices(
                camera_config.get("type", "Webcam")
            )
            self.add_combox_item(
                self.ui.combo_id_camera,
                id_camera,
            )
            self.set_combobox_text(
                self.ui.combo_id_camera, camera_config.get("id", "0")
            )
            self.add_combox_item(self.ui.combo_feature, features)
            self.set_combobox_text(
                self.ui.combo_feature, camera_config.get("feature", "")
            )

        # Áp dụng cấu hình lighting
        if "lighting" in config:
            lighting_config = config["lighting"]
            # Đặt giá trị cho các kênh
            channels = lighting_config.get("channels", [10, 10, 10, 10])
            if len(channels) >= 4:
                self.ui.spin_channel_0.setValue(channels[0])
                self.ui.spin_channel_1.setValue(channels[1])
                self.ui.spin_channel_2.setValue(channels[2])
                self.ui.spin_channel_3.setValue(channels[3])

    def init_camera(self, camera_type, camera_id, camera_feature):
        """
        Khởi tạo camera với thông số từ giao diện.
        """
        try:
            # Ghi log thông số camera
            self.ui_logger.info(
                f"Khởi tạo camera: Type={camera_type}, ID={camera_id}, Feature={camera_feature}"
            )

            # Khởi tạo camera thread với thông số từ giao diện
            if camera_type == "Webcam":
                self.camera_thread = CameraThread(
                    camera_type, {"id": camera_id, "feature": camera_feature,}
                )
            elif camera_type == "HIK":
                # Cấu hình đặc biệt cho camera HIK nếu cần
                self.camera_thread = CameraThread(
                    camera_type,
                    {
                        "id": camera_id,
                        "feature": f"resources/cameras/HIK/{camera_feature}.ini",
                    },
                )
            elif camera_type == "SODA":
                # Cấu hình đặc biệt cho camera SODA nếu cần
                self.camera_thread = CameraThread(
                    camera_type,
                    {
                        "id": camera_id,
                        "feature": f"resources/cameras/SODA/{camera_feature}.ini",
                    },
                )
            else:
                # Mặc định sử dụng Webcam
                self.ui_logger.warning(
                    f"Loại camera {camera_type} không được hỗ trợ, sử dụng Webcam mặc định"
                )
                self.camera_thread = CameraThread("Webcam", {"id": "0", "feature": ""})

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo camera: {str(e)}")
            return False
        
    def set_combobox_text(self, combobox, text):
        """
        Hàm phụ trợ để đặt giá trị văn bản cho combobox.

        Args:
            combobox (QComboBox): Combobox cần đặt giá trị
            text (str): Giá trị văn bản cần đặt
        """
        index = combobox.findText(text)
        if index >= 0:
            combobox.setCurrentIndex(index)

    def add_combox_item(self, combobox, items: list):
        combobox.clear()
        for item in items:
            combobox.addItem(item)
        
    def find_camera_devices(self, type: str):
        devices = get_camera_devices(type)

        if devices is not None:
            id_camera = list(devices.keys())

            feature_dir = "resources/cameras/" + type
            if os.path.exists(feature_dir):
                features = [
                    name.split('.')[0]
                    for name in os.listdir(feature_dir)
                    if name.endswith(".ini") or name.endswith(".pfs")
                ]
                features.append("")
        if not devices:
            id_camera = ["0"]
            features = [""]

        return id_camera, features

    def load_camera_devices(self, type: str):
        id_camera, features = self.find_camera_devices(type)
        self.add_combox_item(self.ui.combo_id_camera, id_camera)
        self.add_combox_item(self.ui.combo_feature, features)
        self.ui.combo_feature.setCurrentIndex(0)

    def on_change_camera_type(self):
        """Xử lý sự kiện khi thay đổi lựa chọn trong combo_type_camera."""
        print("on_change_camera_type")
        type = self.ui.combo_type_camera.currentText()
        self.load_camera_devices(type)

    def on_click_open_camera(self):
        if self.ui.btn_open_camera.text() == "Open":
            self.open_camera()
        else:
            self.close_camera()

    def open_camera(self):
        try:
            # Lấy thông số từ giao diện
            camera_type = self.ui.combo_type_camera.currentText()
            camera_id = self.ui.combo_id_camera.currentText()
            camera_feature = self.ui.combo_feature.currentText()
            self.init_camera(camera_type, camera_id, camera_feature)
            # self.camera_thread = CameraThread()
            self.camera_thread.open_camera()

            self.ui.btn_open_camera.setText("Close")
            self.ui.btn_open_camera.setProperty("class", "danger")
            update_style(self.ui.btn_open_camera)
            self.ui.btn_start_camera.setEnabled(True)
            self.ui.btn_test_camera.setEnabled(True)

            self.ui_logger.info("Camera opened successfully")
        except Exception as e:
            self.ui_logger.error(f"Error Opening Camera: {e}")

    def close_camera(self):
        try:
            self.camera_thread.close_camera()
            self.camera_thread = None

            self.ui.btn_open_camera.setText("Open")
            self.ui.btn_open_camera.setProperty("class", "success")
            update_style(self.ui.btn_open_camera)
            self.ui.btn_start_camera.setEnabled(False)
            self.ui.btn_test_camera.setEnabled(False)

            self.ui_logger.info("Camera closed")
        except Exception as e:
            self.ui_logger.error(f"Error Closing Camera: {e}")

    def on_click_start_camera(self):
        if self.ui.btn_start_camera.text() == "Start":
            self.start_camera()
        else:
            self.stop_camera()

    def start_camera(self):
        try:
            self.camera_thread.frameCaptured.connect(self.update_frame)
            self.camera_thread.start()

            self.ui.btn_start_camera.setText("Stop")
            self.ui.btn_start_camera.setProperty("class", "danger")
            update_style(self.ui.btn_start_camera)
            self.ui.btn_open_camera.setEnabled(False)
            self.ui.btn_test_camera.setEnabled(False)

            self.ui_logger.info("Camera stream started")

        except Exception as e:
            self.ui_logger.error(f"Error Start Camera: {e}")

    def stop_camera(self):
        try:
            self.camera_thread.stop_camera()
            self.camera_thread.frameCaptured.disconnect()

            self.ui.btn_start_camera.setText("Start")
            self.ui.btn_start_camera.setProperty("class", "success")
            update_style(self.ui.btn_start_camera)
            self.ui.btn_open_camera.setEnabled(True)
            self.ui.btn_test_camera.setEnabled(True)

            self.ui_logger.info("Camera stream stopped")
        except Exception as e:
            self.ui_logger.error(f"Error Stop Camera: {e}")

    def update_frame(self, frame):
        self.current_image = frame

        self.canvas_screen.load_pixmap(ndarray2pixmap(self.current_image))

    def on_click_test_camera(self):
        try:
            if not self.camera_thread:
                self.ui_logger.warning("Camera is not open")
                return

            self.current_image = self.camera_thread.grab_camera()
            if self.current_image is None:
                self.ui_logger.error("Failed to capture image")
                return

            self.canvas_screen.load_pixmap(ndarray2pixmap(self.current_image))
        except Exception as e:
            self.ui_logger.error(f"Error Test Camera: {e}")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    win = CameraDlg()
    win.show()
    sys.exit(app.exec_())