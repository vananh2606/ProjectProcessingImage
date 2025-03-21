import os
import sys
import time
import json
import logging
import threading
import cv2 as cv
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QTabWidget,
    QFileDialog,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QScrollArea,
    QListWidgetItem,
)
from PyQt5.QtCore import Qt, QFile, pyqtSignal, QSize
from PyQt5.QtGui import QImage, QPixmap, QIcon
from functools import partial
from collections import namedtuple

from ui.MainWindowUI import Ui_MainWindow

sys.path.append("libs")
from libs.constants import *
from libs.canvas import WindowCanvas, Canvas
from libs.shape import Shape
from libs.ui_utils import load_style_sheet, update_style, add_scroll, ndarray2pixmap
from libs.log_model import setup_logger
from libs.image_converter import ImageConverter
from libs.tcp_server import Server
from libs.camera_thread import CameraThread
from libs.light_controller import LCPController, DCPController

RESULT = namedtuple(
    "result",
    [
        "camera",
        "model",
        "code",
        "src",
        "dst",
        "bin",
        "result",
        "time_check",
        "error_type",
        "config",
    ],
    defaults=10 * [None],
)


class MainWindow(QMainWindow):
    signalResultAuto = pyqtSignal(object)
    signalResultTeaching = pyqtSignal(object)

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.initParameters()
        self.initUi()
        self.connectUi()

    def initParameters(self):
        # Logger and Log Signals
        self.project_name = "Project Name"
        self.log_path = "logs\\logfile.log"
        self.ui_logger, self.ui_logger_text = setup_logger(
            self.ui.list_widget_log,
            self.project_name,
            self.log_path,
        )

        # Server
        self.host = "127.0.0.1"
        self.port = 8080
        self.tcp_server = Server(
            host=self.host,
            port=self.port,
            logger=self.ui_logger,
            log_signals=self.ui_logger_text,
        )

        # Camera
        self.camera_thread = None

        # Image
        self.current_image = None
        self.file_paths = []

        # Lighting
        self.com_light = "COM9"
        # self.baud_light = 9600
        self.baud_light = 19200
        # self.light_controller = LCPController(com=self.com_light, baud=self.baud_light)
        self.light_controller = DCPController(com=self.com_light, baud=self.baud_light)

        # Threading
        self._b_trigger_auto = False
        self._b_trigger_teaching = False
        self._b_stop_auto = False
        self._b_stop_teaching = False

        # Time
        self.t_start = 0.0

        # Result
        self.final_result: RESULT = None

    def initUi(self):
        # Theme
        self.load_theme()

        # Dock
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # Button
        self.ui.btn_start.setProperty("class", "success")
        self.ui.btn_stop.setProperty("class", "danger")
        self.ui.btn_reset.setProperty("class", "primary")
        self.ui.btn_add.setProperty("class", "primary")
        self.ui.btn_delete.setProperty("class", "danger")
        self.ui.btn_save.setProperty("class", "success")
        self.ui.btn_open_camera.setProperty("class", "success")
        self.ui.btn_start_camera.setProperty("class", "success")
        self.ui.btn_test_camera.setProperty("class", "primary")
        self.ui.btn_load_image.setProperty("class", "default")
        self.ui.btn_open_folder.setProperty("class", "default")
        self.ui.btn_capture.setProperty("class", "default")
        self.ui.btn_refesh.setProperty("class", "primary")
        self.ui.btn_start_teaching.setProperty("class", "success")
        self.ui.btn_open_light.setProperty("class", "success")
        self.ui.btn_connect_server.setProperty("class", "success")
        self.ui.btn_send_client.setProperty("class", "primary")
        self.ui.btn_connect_database.setProperty("class", "success")

        # Canvas
        self.canvas_src = Canvas()
        self.ui.verticalLayoutImageSRC.addWidget(WindowCanvas(self.canvas_src))
        self.canvas_binary = Canvas()
        self.ui.verticalLayoutImageBinary.addWidget(WindowCanvas(self.canvas_binary))
        self.canvas_dst = Canvas()
        self.ui.verticalLayoutImageDST.addWidget(WindowCanvas(self.canvas_dst))
        self.canvas_auto = Canvas()
        self.ui.verticalLayoutScreenAuto.addWidget(WindowCanvas(self.canvas_auto))

        # # ScrollBar
        # scroll_bar_database = add_scroll(self.ui.table_widget_database)
        # self.ui.verticalLayoutDatabase.addWidget(scroll_bar_database)

    def connectUi(self):
        # Button
        self.ui.btn_start.clicked.connect(self.on_click_start)
        self.ui.btn_stop.clicked.connect(self.on_click_stop)
        self.ui.btn_reset.clicked.connect(self.on_click_reset)
        self.ui.btn_add.clicked.connect(self.on_click_add)
        self.ui.btn_delete.clicked.connect(self.on_click_delete)
        self.ui.btn_save.clicked.connect(self.on_click_save)
        self.ui.btn_open_camera.clicked.connect(self.on_click_open_camera)
        self.ui.btn_start_camera.clicked.connect(self.on_click_start_camera)
        self.ui.btn_test_camera.clicked.connect(self.on_click_test_camera)
        self.ui.btn_load_image.clicked.connect(self.on_click_load_image)
        self.ui.btn_open_folder.clicked.connect(self.on_click_open_folder)
        self.ui.btn_capture.clicked.connect(self.on_click_capture)
        self.ui.btn_refesh.clicked.connect(self.on_click_refesh)
        self.ui.btn_start_teaching.clicked.connect(self.on_click_start_teaching)
        self.ui.btn_open_light.clicked.connect(self.on_click_open_light)
        self.ui.btn_connect_server.clicked.connect(self.on_click_connect_server)
        self.ui.btn_send_client.clicked.connect(self.on_click_send_client)
        self.ui.btn_connect_database.clicked.connect(self.on_click_connect_database)

        # Combobox
        self.ui.combo_model.currentIndexChanged.connect(self.on_change_model)
        self.ui.combo_model_setting.currentIndexChanged.connect(
            self.on_change_model_setting
        )

        self.ui.list_widget_image.itemSelectionChanged.connect(
            self.display_list_widget_image
        )

        # Server
        self.tcp_server.clientConnected.connect(
            lambda host, address: print(
                f"Client kết nối HOST: {host} - ADDRESS:{address}"
            )
        )
        self.tcp_server.clientDisconnected.connect(
            lambda host, address: print(
                f"Client ngắt kết nối HOST: {host} - ADDRESS:{address}"
            )
        )
        self.tcp_server.dataReceived.connect(
            lambda host, address, data: self.handle_received_data(host, address, data)
        )
        self.tcp_server.serverStarted.connect(
            lambda host, port: print(
                f"Server đã khởi động tại HOST: {host} - PORT: {port}"
            )
        )
        self.tcp_server.serverStopped.connect(lambda: print("Server đã dừng"))

    def load_theme(self):
        self.ui.actionLight.triggered.connect(partial(self.set_theme, "light"))
        self.ui.actionDark.triggered.connect(partial(self.set_theme, "dark"))
        self.ui.actionRainbow.triggered.connect(partial(self.set_theme, "rainbow"))

    def set_theme(self, theme: str):
        if theme == "light":
            path = "resources/themes/light_theme.qss"
            load_style_sheet(path, QApplication.instance())
        elif theme == "dark":
            path = "resources/themes/dark_theme.qss"
            load_style_sheet(path, QApplication.instance())
        elif theme == "rainbow":
            path = "resources/themes/rainbow_theme.qss"
            load_style_sheet(path, QApplication.instance())

    def write_log(self):
        """Ghi thử một số log"""
        self.ui_logger_text.textSignal.emit("Một thông báo khác", None)
        self.ui_logger_text.textSignal.emit("Một thông báo khác", "DEBUG")
        self.ui_logger_text.textSignal.emit("Một thông báo khác", "INFO")
        self.ui_logger_text.textSignal.emit("Một thông báo khác", "WARNING")
        self.ui_logger_text.textSignal.emit("Một thông báo khác", "ERROR")
        self.ui_logger_text.textSignal.emit("Một thông báo khác", "CRITICAL")
        self.ui_logger.debug("Đây là log DEBUG")
        self.ui_logger.info("Đây là log INFO")
        self.ui_logger.warning("Đây là log WARNING")
        self.ui_logger.error("Đây là log ERROR")
        self.ui_logger.critical("Đây là log CRITICAL")

    def handle_received_data(self, host, address, data):
        print(f"Nhận từ HOST: {host} - ADDRESS:{address}: {data}")
        if data == "Check":
            self.tcp_server.send_to_client(
                (host, int(address)), "Đã nhận dữ liệu của bạn"
            )

    def start_elappsed_time(self):
        self.t_start = time.time()

    def get_elappsed_time(self):
        self.ui_logger.debug(f"Get elappsed_time: {time.time() - self.t_start}")
        return time.time() - self.t_start

    @property
    def b_trigger_auto(self):
        self.ui_logger.debug(f"Get b_trigger_auto: {self._b_trigger_auto}")
        return self._b_trigger_auto

    @b_trigger_auto.setter
    def b_trigger_auto(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_trigger_auto = boolean
        self.ui_logger.debug(f"Set b_trigger_auto: {self._b_trigger_auto}")

    @property
    def b_trigger_teaching(self):
        self.ui_logger.debug(f"Get b_trigger_teaching: {self._b_trigger_teaching}")
        return self._b_trigger_teaching

    @b_trigger_teaching.setter
    def b_trigger_teaching(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_trigger_teaching = boolean
        self.ui_logger.debug(f"Set b_trigger_teaching: {self._b_trigger_teaching}")

    @property
    def b_stop_auto(self):
        self.ui_logger.debug(f"Get b_stop_auto: {self._b_stop_auto}")
        return self._b_stop_auto

    @b_stop_auto.setter
    def b_stop_auto(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_stop_auto = boolean
        self.ui_logger.debug(f"Set b_stop_auto: {self._b_stop_auto}")

    @property
    def b_stop_teaching(self):
        self.ui_logger.debug(f"Get b_stop_teaching: {self._b_stop_teaching}")
        return self._b_stop_teaching

    @b_stop_teaching.setter
    def b_stop_teaching(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_stop_teaching = boolean
        self.ui_logger.debug(f"Set b_stop_teaching: {self._b_stop_teaching}")

    def on_click_start(self):
        self.get_config()

    def on_click_stop(self):
        pass

    def on_click_reset(self):
        pass

    def on_click_start_teaching(self):
        pass

    def on_click_refesh(self):
        pass

    def get_config(self):
        """
        Gets the current configuration of the application.
        This includes shapes on the canvas, module settings, and font configuration.

        Returns:
            dict: Dictionary containing the current configuration
        """
        config = {}

        # Get shapes from canvas
        config["shapes"] = {
            shape.label: shape.cvBox for shape in self.canvas_auto.shapes
        }

        # Get module configurations
        config["modules"] = {
            "camera": {
                "type": self.ui.combo_type_camera.currentText(),
                "id": self.ui.combo_id_camera.currentText(),
                "feature": self.ui.combo_feature.currentText(),
            },
            "lighting": {
                "controller": self.ui.combo_controller.currentText(),
                "com": self.ui.combo_comport.currentText(),
                "baudrate": self.ui.combo_baudrate.currentText(),
                "delay": self.ui.spin_delay.value(),
                "channels": [
                    self.ui.spin_channel_0.value(),
                    self.ui.spin_channel_1.value(),
                    self.ui.spin_channel_2.value(),
                    self.ui.spin_channel_3.value(),
                ],
            },
            "system": {
                "log_dir": self.ui.line_log_dir.text(),
                "log_size": self.ui.line_log_size.text(),
                "database_path": self.ui.line_database_path.text(),
                "auto_start": self.ui.check_auto_start.isChecked(),
            },
            "server": {
                "host": self.ui.line_host_server.text(),
                "port": self.ui.line_port_server.text(),
                "client": self.ui.combo_select_client.currentText(),
                "message": self.ui.line_message.text(),
            },
        }

        # Get font configuration
        config["font"] = {
            "radius": Shape.RADIUS,
            "thickness": Shape.THICKNESS,
            "font_size": Shape.FONT_SIZE,
            "min_size": Shape.MIN_SIZE,
        }

        # Load font config from file if it exists
        if os.path.exists(FONT_CONFIG_PATH):
            try:
                with open(FONT_CONFIG_PATH, "r") as f:
                    config["font"] = json.load(f)
            except Exception as e:
                self.ui_logger.error(f"Error loading font config: {e}")

        # Get model settings
        config["model"] = {
            "current": self.ui.combo_model.currentText(),
            "setting": self.ui.combo_model_setting.currentText(),
        }

        self.ui_logger.debug(
            f"Get config: {json.dumps(config, indent=4, ensure_ascii=False)}"
        )

        return config

    def set_config(self, config):
        """
        Sets the application configuration based on the provided config dictionary.

        Args:
            config (dict): Configuration dictionary to apply
        """
        try:
            # Apply shapes to canvas if they exist
            if "shapes" in config:
                # Clear existing shapes
                self.canvas_auto.shapes.clear()

                # Add shapes from config
                for label, box in config["shapes"].items():
                    shape = Shape(label=label)
                    shape.cvBox = box
                    self.canvas_auto.shapes.append(shape)

                # Update canvas
                self.canvas_auto.update()

            # Apply module configurations
            if "modules" in config:
                modules = config["modules"]

                # Apply camera settings
                if "camera" in modules:
                    camera = modules["camera"]

                    index = self.ui.combo_type_camera.findText(camera.get("type", ""))
                    if index >= 0:
                        self.ui.combo_type_camera.setCurrentIndex(index)

                    index = self.ui.combo_id_camera.findText(camera.get("id", ""))
                    if index >= 0:
                        self.ui.combo_id_camera.setCurrentIndex(index)

                    index = self.ui.combo_feature.findText(camera.get("feature", ""))
                    if index >= 0:
                        self.ui.combo_feature.setCurrentIndex(index)

                # Apply lighting settings
                if "lighting" in modules:
                    lighting = modules["lighting"]

                    index = self.ui.combo_controller.findText(
                        lighting.get("controller", "")
                    )
                    if index >= 0:
                        self.ui.combo_controller.setCurrentIndex(index)

                    index = self.ui.combo_comport.findText(lighting.get("com", ""))
                    if index >= 0:
                        self.ui.combo_comport.setCurrentIndex(index)

                    index = self.ui.combo_baudrate.findText(
                        lighting.get("baudrate", "")
                    )
                    if index >= 0:
                        self.ui.combo_baudrate.setCurrentIndex(index)

                    self.ui.spin_delay.setValue(lighting.get("delay", 100))

                    channels = lighting.get("channels", [0, 0, 0, 0])
                    if len(channels) >= 4:
                        self.ui.spin_channel_0.setValue(channels[0])
                        self.ui.spin_channel_1.setValue(channels[1])
                        self.ui.spin_channel_2.setValue(channels[2])
                        self.ui.spin_channel_3.setValue(channels[3])

                # Apply system settings
                if "system" in modules:
                    system = modules["system"]

                    self.ui.line_log_dir.setText(system.get("log_dir", ""))
                    self.ui.line_log_size.setText(system.get("log_size", ""))
                    self.ui.line_database_path.setText(system.get("database_path", ""))
                    self.ui.check_auto_start.setChecked(system.get("auto_start", False))

                # Apply server settings
                if "server" in modules:
                    server = modules["server"]

                    self.ui.line_host_server.setText(server.get("host", "127.0.0.1"))
                    self.ui.line_port_server.setText(server.get("port", "8080"))

            # Apply font configuration
            if "font" in config:
                font = config["font"]

                Shape.RADIUS = font.get("radius", Shape.RADIUS)
                Shape.THICKNESS = font.get("thickness", Shape.THICKNESS)
                Shape.FONT_SIZE = font.get("font_size", Shape.FONT_SIZE)
                Shape.MIN_SIZE = font.get("min_size", Shape.MIN_SIZE)

                # Save font config to file
                try:
                    with open(FONT_CONFIG_PATH, "w") as f:
                        json.dump(font, f, indent=4, ensure_ascii=False)
                except Exception as e:
                    self.ui_logger.error(f"Error saving font config: {e}")

            # Apply model settings
            if "model" in config:
                model = config["model"]

                index = self.ui.combo_model.findText(model.get("current", ""))
                if index >= 0:
                    self.ui.combo_model.setCurrentIndex(index)

                index = self.ui.combo_model_setting.findText(model.get("setting", ""))
                if index >= 0:
                    self.ui.combo_model_setting.setCurrentIndex(index)

            self.ui_logger.info("Configuration applied successfully")

        except Exception as e:
            self.ui_logger.error(f"Error applying configuration: {e}")

    def load_model(self, config):
        pass

    def add_model(self, config):
        pass

    def delete_model(self, config):
        pass

    def save_model(self, config):
        pass

    def on_click_add(self):
        pass

    def on_click_delete(self):
        pass

    def on_click_save(self):
        pass

    def on_change_model(self):
        pass

    def on_change_model_setting(self):
        pass

    def on_click_open_folder(self):
        try:
            # Hộp thoại chọn thư mục
            folder_path = QFileDialog.getExistingDirectory(self, "Select Folder")
            if folder_path:
                # Lấy danh sách file ảnh từ thư mục
                self.file_paths.clear()  # Xóa dữ liệu cũ
                self.ui.list_widget_image.clear()  # Xóa mục cũ trong QListWidget
                image_extensions = [".png", ".jpg", ".jpeg", ".bmp", ".gif"]

                self.ui_logger.debug(f"Loading images from: {folder_path}")

                image_count = 0
                for file_name in os.listdir(folder_path):
                    if any(file_name.lower().endswith(ext) for ext in image_extensions):
                        file_path = os.path.join(folder_path, file_name)
                        self.file_paths.append(file_path)

                        # Thêm mục mới vào QListWidget
                        list_item = QListWidgetItem(file_name)
                        self.ui.list_widget_image.addItem(list_item)
                        image_count += 1

                self.ui_logger.debug(f"Loaded {image_count} images from folder")
        except Exception as e:
            self.ui_logger.error(f"Error Load Folder: {e}")

    def display_list_widget_image(self):
        try:
            # Hiển thị ảnh trong list _widget_image
            selected_items = self.ui.list_widget_image.selectedItems()
            if selected_items:
                item = selected_items[0]
                index = self.ui.list_widget_image.row(item)
                file_path = self.file_paths[index]
                self.current_image = cv.imread(file_path)

                # Cập nhật log
                self.ui_logger.debug(f"Loaded image: {os.path.basename(file_path)}")

                self.canvas_src.load_pixmap(ndarray2pixmap(self.current_image))

        except Exception as e:
            self.ui_logger.error(f"Error Display List Image: {e}")

    def on_click_load_image(self):
        try:
            # Hộp thoại chọn ảnh
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Image", "", "Images (*.png *.jpg *.jpeg)"
            )
            if file_path:
                self.current_image = cv.imread(file_path)

                # Cập nhật log
                self.ui_logger.debug(f"Loaded image: {os.path.basename(file_path)}")

                self.canvas_src.load_pixmap(ndarray2pixmap(self.current_image))

        except Exception as e:
            self.ui_logger.error(f"Error Load Image: {e}")

    def on_click_open_camera(self):
        if self.ui.btn_open_camera.text() == "Open":
            self.open_camera()
        else:
            self.close_camera()

    def open_camera(self):
        try:
            self.camera_thread = CameraThread("Webcam", {"id": "0", "feature": ""})
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
            self.ui.btn_load_image.setEnabled(False)
            self.ui.btn_open_folder.setEnabled(False)
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
            self.ui.btn_load_image.setEnabled(True)
            self.ui.btn_open_folder.setEnabled(True)
            self.ui.btn_test_camera.setEnabled(True)

            self.ui_logger.info("Camera stream stopped")
        except Exception as e:
            self.ui_logger.error(f"Error Stop Camera: {e}")

    def update_frame(self, frame):
        self.current_image = frame

        self.canvas_src.load_pixmap(ndarray2pixmap(self.current_image))

    def on_click_test_camera(self):
        try:
            if not self.camera_thread:
                self.ui_logger.warning("Camera is not open")
                return

            self.current_image = self.camera_thread.grab_camera()
            if self.current_image is None:
                self.ui_logger.error("Failed to capture image")
                return

            self.canvas_src.load_pixmap(ndarray2pixmap(self.current_image))
        except Exception as e:
            self.ui_logger.error(f"Error Test Camera: {e}")

    def on_click_capture(self):
        try:
            if self.current_image is None:
                self.ui_logger.error("Failed to capture image")
                return

            # Create default filename with timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            default_filename = f"Image_{timestamp}.jpg"

            # Open save file dialog
            file_dialog = QFileDialog()
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setNameFilter("Images (*.jpg *.png *.bmp)")
            file_dialog.setDefaultSuffix("jpg")
            file_dialog.selectFile(default_filename)

            if file_dialog.exec() == QFileDialog.DialogCode.Accepted:
                filename = file_dialog.selectedFiles()[0]
                # Save the image
                cv.imwrite(filename, self.current_image)

                self.ui_logger.info(f"Image captured and saved to: {filename}")

        except Exception as e:
            self.ui_logger.error(f"Error Capture: {e}")

    def on_click_open_light(self):
        if self.ui.btn_open_light.text() == "Open":
            self.open_light()
        else:
            self.close_light()

    def open_light(self):
        try:
            print(self.light_controller.open())
            self.light_controller.on_channel(0, 10)

            self.ui.btn_open_light.setText("Close")
            self.ui.btn_open_light.setProperty("class", "danger")
            update_style(self.ui.btn_open_light)
        except Exception as e:
            self.ui_logger.error(f"Error Open Light: {e}")

    def close_light(self):
        try:
            self.light_controller.off_channel(0)
            # self.light_controller.close()

            self.ui.btn_open_light.setText("Open")
            self.ui.btn_open_light.setProperty("class", "success")
            update_style(self.ui.btn_open_light)
        except Exception as e:
            self.ui_logger.error(f"Error Close Light: {e}")

    def on_click_connect_server(self):
        if self.ui.btn_connect_server.text() == "Connect":
            self.connect_server()
        else:
            self.disconnect_server()

    def connect_server(self):
        try:
            self.tcp_server.start()

            self.ui.btn_connect_server.setText("Disconnect")
            self.ui.btn_connect_server.setProperty("class", "danger")
            update_style(self.ui.btn_connect_server)
        except Exception as e:
            self.ui_logger.error(f"Error Connect Server: {e}")

    def disconnect_server(self):
        try:
            self.tcp_server.stop()

            self.ui.btn_connect_server.setText("Connect")
            self.ui.btn_connect_server.setProperty("class", "success")
            update_style(self.ui.btn_connect_server)
        except Exception as e:
            self.ui_logger.error(f"Error Disconnect Server: {e}")

    def on_click_send_client(self):
        try:
            self.tcp_server.send_to_all("Hello")
        except Exception as e:
            self.ui_logger.error(f"Error Send Client: {e}")

    def on_click_connect_database(self):
        if self.ui.btn_connect_database.text() == "Connect":
            self.connect_database()
        else:
            self.disconnect_database()

    def connect_database(self):
        try:
            self.ui.btn_connect_database.setText("Disconnect")
            self.ui.btn_connect_database.setProperty("class", "danger")
            update_style(self.ui.btn_connect_database)
        except Exception as e:
            self.ui_logger.error(f"Error Connect Database: {e}")

    def disconnect_database(self):
        try:
            self.ui.btn_connect_database.setText("Connect")
            self.ui.btn_connect_database.setProperty("class", "success")
            update_style(self.ui.btn_connect_database)
        except Exception as e:
            self.ui_logger.error(f"Error Disconnect Database: {e}")

    def closeEvent(self, event):
        return super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.setWindowTitle("Project Name")
    window.setWindowIcon(QIcon("resources/icons/cyber-eye.png"))
    load_style_sheet("resources/themes/light_theme.qss", QApplication.instance())
    window.show()
    sys.exit(app.exec_())
