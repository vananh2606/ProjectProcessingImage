import os
import gc
import sys
import time
from pathlib import Path
import json
import shutil
import random
import logging
import enum
import pandas as pd
import xlsxwriter
import serial
import serial.tools
import serial.tools.list_ports
import threading
import cv2 as cv
from PyQt5.QtWidgets import (
    QMainWindow,
    QDialog,
    QApplication,
    QWidget,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QScrollArea,
    QListWidgetItem,
    QProgressBar
)
from PyQt5.QtCore import Qt, QThread, QTimer, QFile, pyqtSignal, QSize, QPointF
from PyQt5.QtGui import QImage, QPixmap, QIcon, QColor, QBrush, QFont
from functools import partial
from collections import namedtuple
from typing import List

sys.path.append("ui")
sys.path.append("libs")
from ui.MainWindowUI import Ui_MainWindow
from libs.loading import LoadingDialog

from libs.camera_dlg import CameraDlg

class ImportThread(QThread):
    progress = pyqtSignal(int)  # Signal to update the progress bar
    finished = pyqtSignal()     # Signal to notify when import is done

    def thread_import(self):
        # Import your module here
        import ultralytics
        from ultralytics import YOLO

    def run(self):
        threading.Thread(target=self.thread_import, daemon=True).start()
        # Simulate the import process with a loop
        for i in range(99):
            time.sleep(0.1)  # Simulate delay
            self.progress.emit(i)
        self.finished.emit()

class ImportProgressBar(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YOLO Import Progress")
        self.setGeometry(500, 200, 400, 300)

        self.init_ui()
        self.start_import_thread()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        layout = QVBoxLayout()
        self.progress_label = QLabel("Importing YOLO module, please wait...")
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)

        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)

        self.central_widget.setLayout(layout)

    def start_import_thread(self):
        self.import_thread = ImportThread()
        self.import_thread.progress.connect(self.update_progress)
        self.import_thread.finished.connect(self.import_finished)
        self.import_thread.start()

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def import_finished(self):
        self.progress_label.setText("YOLO module imported successfully!")
        self.progress_bar.setValue(100)
        self.close()

sys.path.append("libs")
sys.path.append("ui")
sys.path.append("cameras")

from libs.constants import *
from libs.canvas import WindowCanvas, Canvas
from libs.shape import Shape
from libs.ui_utils import load_style_sheet, update_style, add_scroll, ndarray2pixmap
from libs.utils import scan_dir
from libs.logger import Logger
from libs.image_converter import ImageConverter
from libs.tcp_server import Server
from libs.vision import YoloInference, plot_results
from libs.database_lite import *
from cameras import HIK, SODA, Webcam, get_camera_devices
from libs.camera_thread import CameraThread
from libs.light_controller import LCPController, DCPController
from libs.serial_controller import SerialController
from libs.vision_controller import VisionController
from libs.io_controller import IOController, OutPorts, InPorts, PortState, IOType

from libs.auto_scanner_dlg import AutoScannerDlg
from libs.pop_up_dlg import PopUpDlg


app = QApplication(sys.argv)
load_style_sheet("resources/themes/dark_theme.qss", QApplication.instance())

window = ImportProgressBar()
window.show()
app.exec_()

RESULT = namedtuple(
    "result",
    [
        "step",
        "time_check",
        "model_name",
        "result",
        "src",
        "binary",
        "dst",
        "code_sn",
        "weight",
        "error_type",
        "config",
    ],
    defaults=10 * [None],
)

DATA_IMAGE = namedtuple(
    "data_image",
    [
        "path",
        "src",
        "binary",
        "dst",
    ],
    defaults=4 * [None],
)

class TypeLog(enum.Enum):
    DEFAULT = 0
    DEBUG = 1
    INFO = 2
    WARNING = 3
    ERROR = 4
    CRITICAL = 5

class ColorType(enum.Enum):
    GRAY = (cv.COLOR_BGR2GRAY, "GRAY")
    RGB = (cv.COLOR_BGR2RGB, "RGB")
    BGR = (cv.COLOR_RGB2BGR, "BGR")
    HSV = (cv.COLOR_BGR2HSV, "HSV")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label

    @classmethod
    def from_label(cls, label: str):
        for item in cls:
            if item.label == label:
                return item
        raise ValueError(f"Không tìm thấy kiểu color từ label: {label}")

    @classmethod
    def from_value(cls, value: int):
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"Không tìm thấy kiểu color từ giá trị: {value}")
    
    @classmethod
    def list_labels(cls):
        return [item.label for item in cls]
    
class BlurType(enum.Enum):
    GAUSSIAN = (cv.GaussianBlur, "Gaussian Blur")
    MEDIAN = (cv.medianBlur, "Median Blur")
    BILATERAL = (cv.blur, "Average Blur")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label

    @classmethod
    def from_label(cls, label: str):
        for item in cls:
            if item.label == label:
                return item
        raise ValueError(f"Không tìm thấy kiểu blur từ label: {label}")

    @classmethod
    def from_value(cls, value):
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"Không tìm thấy kiểu blur từ giá trị: {value}")
    
    @classmethod
    def list_labels(cls):
        return [item.label for item in cls]

class ThresholdType(enum.Enum):
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
    
class MorphType(enum.Enum):
    ERODE = (cv.MORPH_ERODE, "Erode")
    DILATE = (cv.MORPH_DILATE, "Dilate")
    OPEN = (cv.MORPH_OPEN, "Open")
    CLOSE = (cv.MORPH_CLOSE, "Close")

    def __init__(self, value, label):
        self._value_ = value
        self.label = label
    
    @classmethod
    def from_label(cls, label: str):
        for item in cls:
            if item.label == label:
                return item
        raise ValueError(f"Không tìm thấy kiểu morph từ label: {label}")
    
    @classmethod
    def from_value(cls, value: int):
        for item in cls:
            if item.value == value:
                return item
        raise ValueError(f"Không tìm thấy kiểu morph từ giá trị: {value}")
    
    @classmethod
    def list_labels(cls):
        return [item.label for item in cls] 


class MainWindow(QMainWindow):
    signalResultAuto = pyqtSignal(object, str)
    signalResultTeaching = pyqtSignal(object)

    signalShowPopup = pyqtSignal(str, str, str)

    signalChangeLabelResult = pyqtSignal(str)
    signalChangeLight = pyqtSignal(object)

    signalLogUI = pyqtSignal(TypeLog, str)

    loadProgress = pyqtSignal(int, str)
    finishProgress = pyqtSignal()

    def __init__(self):
        super(MainWindow, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        # Tạo thanh trạng thái với progress bar
        self.status_label = QLabel()
        self.status_label.setText("Project Name")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_progress_bar = QProgressBar()
        self.status_progress_bar.setTextVisible(True)
        self.status_progress_bar.setMaximumWidth(500)
        self.status_progress_bar.setAlignment(Qt.AlignCenter)
        self.statusBar().addPermanentWidget(self.status_label)
        self.statusBar().addPermanentWidget(self.status_progress_bar)

        # Kết nối signals
        self.loadProgress.connect(self.load_progress)
        self.finishProgress.connect(self.finish_progress)

        self.initParameters()
        self.initUi()
        self.connectUi()

    def initParameters(self):
        # Logger and Log Signals
        self.project_name = "ProjectName"
        self.log_path = "logs"
        self.ui_logger = Logger(name=self.project_name, log_file=self.log_path)

        # Camera
        self.camera_thread = None
        self.camera1 = None
        self.camera2 = None

        # Lighting
        self.light_controller = None

        # Weight Controller
        self.weight_controller = None
        self.weight = None

        # Vision Master
        self.vision_master_controller = None
        self.dataVM = None

        # Scanner Controller
        self.scanner_controller = None
        self.listCodeSN = []

        # Out COM
        self.out_com_controller = None

        # IO Controller
        self.io_controller = None

        # Server
        self.tcp_server = None

        # Model AI
        self.model_ai = None

        # Image
        self.current_image = None
        self.current_image_camera1 = None
        self.current_image_camera2 = None
        self.file_paths = []

        # Threading
        self._b_trigger_weight_auto = False
        self._b_trigger_optic_auto = False
        self._b_trigger_unitbox_auto = False
        self._b_stop_auto = False
        self._b_trigger_teaching = False
        self._b_stop_teaching = False

        # Time
        self.t_start = 0.0

        # Result
        self.final_result: RESULT = None
        self.popup_result = "FAIL"
        self.flag_popup = True

        # Database
        self.database_path = ""

    def initUi(self):
        # Theme
        self.load_theme()

        # Dock
        self.setTabPosition(Qt.AllDockWidgetAreas, QTabWidget.North)

        # TableWidget
        self.ui.table_widget_database.setEditTriggers(QTableWidget.NoEditTriggers)

        # Button
        self.ui.btn_auto_scanner.setProperty("class", "primary")
        self.ui.btn_clear_list.setProperty("class", "primary")
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
        self.ui.btn_open_weight.setProperty("class", "success")
        self.ui.btn_open_vision_master.setProperty("class", "success")
        self.ui.btn_trigger_vision_master.setProperty("class", "primary")
        self.ui.btn_open_scanner.setProperty("class", "success")
        self.ui.btn_open_out_com.setProperty("class", "success")
        self.ui.btn_send_data_out_com.setProperty("class", "primary")
        self.ui.btn_open_io.setProperty("class", "success")
        self.ui.btn_open_all_io.setProperty("class", "primary")
        self.ui.btn_close_all_io.setProperty("class", "primary")
        self.ui.btn_connect_server.setProperty("class", "success")
        self.ui.btn_send_client.setProperty("class", "primary")
        self.ui.btn_create_database.setProperty("class", "primary")
        self.ui.btn_connect_database.setProperty("class", "success")
        self.ui.btn_filter_data.setProperty("class", "primary")
        self.ui.btn_export.setProperty("class", "primary")

        # Label
        self.ui.label_result.setProperty("class", "waiting")
        self.ui.label_result.setStyleSheet("font-size: 40px;")
        self.ui.label_value_weight.setProperty("class", "waiting")
        self.ui.label_weight.setProperty("class", "waiting")
        self.ui.label_model_code.setProperty("class", "waiting")

        # IO
        self.ui.btn_output_1.setProperty("class", "success")
        self.ui.btn_output_1.setText("On")
        self.ui.btn_output_1.setEnabled(False)
        self.ui.btn_output_2.setProperty("class", "success")
        self.ui.btn_output_2.setText("On")
        self.ui.btn_output_2.setEnabled(False)
        self.ui.btn_output_3.setProperty("class", "success")
        self.ui.btn_output_3.setText("On")
        self.ui.btn_output_3.setEnabled(False)
        self.ui.btn_output_4.setProperty("class", "success")
        self.ui.btn_output_4.setText("On")
        self.ui.btn_output_4.setEnabled(False)
        self.ui.btn_output_5.setProperty("class", "success")
        self.ui.btn_output_5.setText("On")
        self.ui.btn_output_5.setEnabled(False)
        self.ui.btn_output_6.setProperty("class", "success")
        self.ui.btn_output_6.setText("On")
        self.ui.btn_output_6.setEnabled(False)
        self.ui.btn_output_7.setProperty("class", "success")
        self.ui.btn_output_7.setText("On")
        self.ui.btn_output_7.setEnabled(False)
        self.ui.btn_output_8.setProperty("class", "success")
        self.ui.btn_output_8.setText("On")
        self.ui.btn_output_8.setEnabled(False)
        self.ui.label_input_1.setProperty("class", "fail")
        self.ui.label_input_1.setText("Off")
        self.ui.label_input_2.setProperty("class", "fail")
        self.ui.label_input_2.setText("Off")
        self.ui.label_input_3.setProperty("class", "fail")
        self.ui.label_input_3.setText("Off")
        self.ui.label_input_4.setProperty("class", "fail")
        self.ui.label_input_4.setText("Off")
        self.ui.label_input_5.setProperty("class", "fail")
        self.ui.label_input_5.setText("Off")
        self.ui.label_input_6.setProperty("class", "fail")
        self.ui.label_input_6.setText("Off")
        self.ui.label_input_7.setProperty("class", "fail")
        self.ui.label_input_7.setText("Off")
        self.ui.label_input_8.setProperty("class", "fail")
        self.ui.label_input_8.setText("Off")

        # ComboBox
        self.ui.combo_model_setting.setEditable(True)
        self.ui.combo_comport_light.setEditable(True)
        self.ui.combo_baudrate_light.setEditable(True)
        self.ui.combo_comport_weight.setEditable(True)
        self.ui.combo_baudrate_weight.setEditable(True)
        self.ui.combo_comport_vision_master.setEditable(True)
        self.ui.combo_baudrate_vision_master.setEditable(True)
        self.ui.combo_comport_scanner.setEditable(True)
        self.ui.combo_baudrate_scanner.setEditable(True)
        self.ui.combo_comport_out_com.setEditable(True)
        self.ui.combo_baudrate_out_com.setEditable(True)
        self.ui.combo_comport_io.setEditable(True)
        self.ui.combo_baudrate_io.setEditable(True)

        # Canvas
        self.canvas_src = Canvas()
        self.ui.verticalLayoutImageSRC.addWidget(WindowCanvas(self.canvas_src))
        self.canvas_binary = Canvas()
        self.ui.verticalLayoutImageBinary.addWidget(WindowCanvas(self.canvas_binary))
        self.canvas_dst = Canvas()
        self.ui.verticalLayoutImageDST.addWidget(WindowCanvas(self.canvas_dst))
        self.canvas_camera1_teaching = Canvas()
        self.ui.verticalLayoutScreenTeaching.addWidget(WindowCanvas(self.canvas_camera1_teaching))
        self.canvas_camera2_teaching = Canvas()
        self.ui.verticalLayoutScreenTeaching.addWidget(WindowCanvas(self.canvas_camera2_teaching))
        self.canvas_camera1_auto = Canvas()
        self.ui.horizontalLayoutScreenAuto.addWidget(WindowCanvas(self.canvas_camera1_auto))
        self.canvas_camera2_auto = Canvas()
        self.ui.horizontalLayoutScreenAuto.addWidget(WindowCanvas(self.canvas_camera2_auto))
        self.canvas_input = Canvas()
        self.ui.verticalLayoutCanvasInput.addWidget(WindowCanvas(self.canvas_input))
        self.canvas_output = Canvas()
        self.ui.verticalLayoutCanvasOutput.addWidget(WindowCanvas(self.canvas_output))

        # Add Camera Config
        self.camera_dlg_1 = CameraDlg(canvas_screen=self.canvas_camera1_teaching)
        self.camera_dlg_2 = CameraDlg(canvas_screen=self.canvas_camera2_teaching)

        self.ui.tabWidgetCameraConfig.addTab(self.camera_dlg_1, "Camera1")
        self.ui.tabWidgetCameraConfig.addTab(self.camera_dlg_2, "Camera2")

        # Model
        self.initialize_models()

    def connectUi(self):
        # Button
        self.ui.btn_auto_scanner.clicked.connect(self.on_click_auto_scanner)
        self.ui.btn_clear_list.clicked.connect(self.on_click_clear_list)
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
        self.ui.btn_open_weight.clicked.connect(self.on_click_open_weight)
        self.ui.btn_open_vision_master.clicked.connect(self.on_click_open_vision_master)
        self.ui.btn_trigger_vision_master.clicked.connect(self.on_click_trigger_vision_master)
        self.ui.btn_open_scanner.clicked.connect(self.on_click_open_scanner)
        self.ui.btn_open_out_com.clicked.connect(self.on_click_open_out_com)
        self.ui.btn_send_data_out_com.clicked.connect(self.on_click_send_data_out_com)
        self.ui.btn_open_io.clicked.connect(self.on_click_open_io)
        self.ui.btn_open_all_io.clicked.connect(self.on_click_open_all_io)
        self.ui.btn_close_all_io.clicked.connect(self.on_click_close_all_io)
        self.ui.btn_connect_server.clicked.connect(self.on_click_connect_server)
        self.ui.btn_send_client.clicked.connect(self.on_click_send_client)
        self.ui.btn_create_database.clicked.connect(self.create_database)
        self.ui.btn_connect_database.clicked.connect(self.on_click_connect_database)
        self.ui.btn_filter_data.clicked.connect(self.filter_data)
        self.ui.btn_export.clicked.connect(self.export_to_excel)

        # IO
        self.ui.btn_output_1.clicked.connect(self.on_click_output_1)
        self.ui.btn_output_2.clicked.connect(self.on_click_output_2)
        self.ui.btn_output_3.clicked.connect(self.on_click_output_3)
        self.ui.btn_output_4.clicked.connect(self.on_click_output_4)
        self.ui.btn_output_5.clicked.connect(self.on_click_output_5)
        self.ui.btn_output_6.clicked.connect(self.on_click_output_6)
        self.ui.btn_output_7.clicked.connect(self.on_click_output_7)
        self.ui.btn_output_8.clicked.connect(self.on_click_output_8)

        # Combobox
        self.ui.combo_model.currentIndexChanged.connect(self.on_change_model)
        self.ui.combo_model_setting.currentIndexChanged.connect(
            self.on_change_model_setting
        )
        self.ui.combo_type_camera.currentIndexChanged.connect(
            self.on_change_camera_type
        )

        # DockWidget
        self.ui.dockWidgetImageBinary.setVisible(False)
        self.ui.dockWidgetViewlLog.setVisible(False)

        # ListWidget
        self.ui.list_widget_image.itemSelectionChanged.connect(
            self.display_list_widget_image
        )

        # TableWidget
        self.ui.table_widget_database.itemSelectionChanged.connect(self.on_item_table_data_selection_changed)

        # Kết nối tín hiệu kết quả
        self.signalResultAuto.connect(self.handle_result_auto)
        self.signalResultTeaching.connect(self.handle_result_teaching)
        self.signalShowPopup.connect(self.show_popup)

        # Kết nối tín hiệu thay đổi Label
        self.signalChangeLabelResult.connect(self.handle_change_label_result)

        # Kết nối tín hiệu thay đổi ánh sáng
        self.signalChangeLight.connect(self.handle_change_light)
        self.change_value_light()

        # Kết nối tín hiệu gửi thông báo
        self.signalLogUI.connect(self.handle_log_ui)

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

    def change_value_light(self):
        self.ui.spin_channel_0.valueChanged.connect(
            lambda value: self.signalChangeLight.emit((0, value))
        )
        self.ui.spin_channel_1.valueChanged.connect(
            lambda value: self.signalChangeLight.emit((1, value)) 
        )
        self.ui.spin_channel_2.valueChanged.connect(
            lambda value: self.signalChangeLight.emit((2, value))
        )
        self.ui.spin_channel_3.valueChanged.connect(
            lambda value: self.signalChangeLight.emit((3, value))
        )

    def load_progress(self, dt=5, status_name=""):
        self.status_progress_bar.setTextVisible(True)
        self.status_label.setText(status_name)
        self.status_progress_bar.setValue(0)
        for i in range(0, 100):
            QTimer.singleShot(dt*i, lambda value=i: self.status_progress_bar.setValue(value+1))
    def finish_progress(self):
        self.status_label.setText("Completed")
        self.status_progress_bar.setValue(0)
        self.status_progress_bar.setTextVisible(False)
        

    def initialize_models(self):
        """
        Khởi tạo danh sách models từ thư mục models.
        Nếu không có model nào, sẽ áp dụng cấu hình mặc định.
        """
        try:
            # Tạo thư mục models nếu chưa tồn tại
            if not os.path.exists("models"):
                os.makedirs("models", exist_ok=True)
                self.ui_logger.info("Đã tạo thư mục models")

            # Xóa tất cả các mục trong combobox
            self.ui.combo_model.clear()
            self.ui.combo_model_setting.clear()

            # Duyệt qua các thư mục trong models
            model_dirs = [
                d
                for d in os.listdir("models")
                if os.path.isdir(os.path.join("models", d))
            ]

            # Thêm các model vào combobox
            valid_models = []
            for model_dir in model_dirs:
                config_path = os.path.join("models", model_dir, "config.json")

                # Chỉ thêm model có file config.json
                if os.path.exists(config_path):
                    self.ui.combo_model.addItem(model_dir)
                    self.ui.combo_model_setting.addItem(model_dir)
                    valid_models.append(model_dir)

            self.ui_logger.info(f"Đã tìm thấy {len(valid_models)} model")

            # Nếu có model, tải model đầu tiên
            if len(valid_models) > 0:
                self.load_model(valid_models[0])
            else:
                # Nếu không có model nào, áp dụng cấu hình mặc định
                self.ui_logger.warning(
                    "Không tìm thấy model nào, áp dụng cấu hình mặc định"
                )
                self.apply_default_config()

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo danh sách models: {str(e)}")
            # Trong trường hợp có lỗi, vẫn áp dụng cấu hình mặc định
            self.apply_default_config()

    def apply_default_config(self):
        """
        Áp dụng cấu hình mặc định cho ứng dụng.
        Được gọi khi không có model nào được tìm thấy hoặc có lỗi khi tải model.
        """
        try:
            # Tạo cấu hình mặc định
            default_config = {
                "shapes": {},
                "modules": {
                    "camera": {
                        "type": "Webcam",
                        "id": "0",
                        "feature": ""
                    },
                    "lighting": {
                        "controller_light": "DCP",
                        "comport_light": "COM15",
                        "baudrate_light": "19200",
                        "delay": 100,
                        "channels": [
                            10,
                            10,
                            10,
                            10
                        ]
                    },
                    "weight": {
                        "comport_weight": "COM14",
                        "baudrate_weight": "9600",
                        "min_weight": "0.036",
                        "max_weight": "0.042",
                        "value_weight": "0.2"
                    },
                    "vision_master": {
                        "comport_vision_master": "COM20",
                        "baudrate_vision_master": "9600",
                        "string_trigger": "TRIGGER"
                    },
                    "scanner": {
                        "comport_scanner": "COM17",
                        "baudrate_scanner": "9600"
                    },
                    "out_com": {
                        "comport_out_com": "COM21",
                        "baudrate_out_com": "9600"
                    },
                    "io": {
                        "comport_io": "COM16",
                        "baudrate_io": "19200"
                    },
                    "server": {
                        "host": "127.0.0.1",
                        "port": "8080"
                    },
                    "system": {
                        "log_dir": "log_database",
                        "log_size": "10",
                        "database_path": "database.db",
                        "auto_start": false
                    },
                    "model_ai": {
                        "model_path": "best_plus",
                        "confidence": "0.75"
                    },
                    "processing": {
                        "color": "GRAY",
                        "blur": {
                            "type_blur": "Gaussian Blur",
                            "kernel_size_blur": 5
                        },
                        "threshold": {
                            "type_threshold": "Thresh Binary",
                            "value_threshold": 127
                        },
                        "morphological": {
                            "type_morph": "Erode",
                            "iteration": 1,
                            "kernel_size_morph": 3
                        }
                    },
                    "camera_config": {
                        "camera1": {
                            "device": {
                                "type": "HIK",
                                "id": "DA5691956",
                                "feature": "Camera_1"
                            },
                            "lighting": {
                                "delay": 200,
                                "channels": [
                                    10,
                                    10,
                                    10,
                                    10
                                ]
                            }
                        },
                        "camera2": {
                            "device": {
                                "type": "HIK",
                                "id": "DA5691962",
                                "feature": "Camera_2"
                            },
                            "lighting": {
                                "delay": 200,
                                "channels": [
                                    10,
                                    10,
                                    10,
                                    10
                                ]
                            }
                        }
                    }
                },
                "font": {
                    "radius": 20,
                    "thickness": 3,
                    "font_size": 25,
                    "min_size": 10
                }
            }

            # Áp dụng cấu hình mặc định
            self.set_config(default_config)
            self.ui_logger.info("Đã áp dụng cấu hình mặc định")

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi áp dụng cấu hình mặc định: {str(e)}")

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

    def init_lighting(self, controller_type, com_port, baud_rate):
        """
        Khởi tạo bộ điều khiển đèn với thông số từ giao diện.
        """
        try:
            # Ghi log thông số lighting
            self.ui_logger.info(
                f"Khởi tạo lighting: Type={controller_type}, COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            if controller_type == "LCP":
                self.light_controller = LCPController(com=com_port, baud=baud_rate)
            elif controller_type == "DCP":
                self.light_controller = DCPController(com=com_port, baud=baud_rate)
            else:
                # Mặc định sử dụng DCP
                self.ui_logger.warning(
                    f"Loại bộ điều khiển {controller_type} không được hỗ trợ, sử dụng DCP mặc định"
                )
                self.light_controller = DCPController(com=com_port, baud=baud_rate)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo lighting: {str(e)}")
            return False
    
    def init_weight(self, com_port, baud_rate):
        try:
            # Ghi log thông số io
            self.ui_logger.info(
                f"Khởi tạo Weight: COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            self.weight_controller = SerialController(com=com_port, baud=baud_rate)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo weight: {str(e)}")
            return False

    def init_vision_master(self, com_port, baud_rate, strTrigger="TRIGGER"):
        try:
            # Ghi log thông số io
            self.ui_logger.info(
                f"Khởi tạo Vision Master: COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            self.vision_master_controller = VisionController(com=com_port, baud=baud_rate, strTrigger=strTrigger)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo vision master: {str(e)}")
            return False
        
    def init_scanner(self, com_port, baud_rate):
        try:
            # Ghi log thông số io
            self.ui_logger.info(
                f"Khởi tạo Scanner: COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            self.scanner_controller = SerialController(com=com_port, baud=baud_rate)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo Scanner: {str(e)}")
            return False
        
    def init_out_com(self, com_port, baud_rate):
        try:
            # Ghi log thông số io
            self.ui_logger.info(
                f"Khởi tạo Out COM: COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            self.out_com_controller = SerialController(com=com_port, baud=baud_rate)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo Scanner: {str(e)}")

    def init_io(self, com_port, baud_rate):
        try:
            # Ghi log thông số io
            self.ui_logger.info(
                f"Khởi tạo IO: COM={com_port}, Baud={baud_rate}"
            )

            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            self.io_controller = IOController(com=com_port, baud=baud_rate)

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo io: {str(e)}")
            return False
    
    def init_server(self, host, port):
        """
        Khởi tạo server với thông số từ giao diện.
        """
        try:
            # Ghi log thông số server
            self.ui_logger.info(f"Khởi tạo server: Host={host}, Port={port}")

            # Khởi tạo server với thông số từ giao diện
            self.tcp_server = Server(
                host=host,
                port=port,
                logger=self.ui_logger,
            )

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo server: {str(e)}")
            return False

    def init_system(self):
        """
        Khởi tạo hệ thống với thông số từ giao diện.
        """
        try:
            # Lấy thông số từ giao diện
            log_dir = self.ui.line_log_dir.text()
            log_size = float(self.ui.line_log_size.text())
            database_path = self.ui.line_database_path.text()
            auto_start = self.ui.check_auto_start.isChecked()

            # Ghi log thông số hệ thống
            self.ui_logger.info(
                f"Khởi tạo hệ thống: LogDir={log_dir}, LogSize={log_size}GB, Database={database_path}, AutoStart={auto_start}"
            )

            # Tạo thư mục log nếu chưa tồn tại
            if not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
                self.ui_logger.info(f"Đã tạo thư mục log: {log_dir}")

            # Cập nhật đường dẫn log nếu khác với hiện tại
            if log_dir != os.path.dirname(self.log_path):
                self.log_path = os.path.join(log_dir, "logfile.log")
                self.ui_logger.info(f"Đã cập nhật đường dẫn log: {self.log_path}")

            # Thiết lập tự động khởi động nếu được chọn
            if auto_start:
                self.ui_logger.info("Tự động khởi động được bật")
            else:
                self.ui_logger.info("Tự động khởi động được tắt")

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo hệ thống: {str(e)}")
            return False
        
    def init_model_ai(self, model_path):
        """
        Khởi tạo model AI với thông số từ giao diện.
        """
        try:
            # Ghi log thông số model AI
            self.ui_logger.info(f"Khởi tạo model AI: Path={model_path}")

            # Khởi tạo model AI với thông số từ giao diện
            self.model_ai = YoloInference(
                model=f"resources/models_ai/{model_path}.pt",
                label=LABEL_CONFIG_PATH,
            )

            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo Model AI: {str(e)}")
            return False
        
    def init_camera_config(self, camera_config: dict):
        """
        Khởi tạo camera với thông số từ giao diện.
        """
        try:
            camera_config1 = camera_config["camera1"]
            camera_type1 = camera_config1["device"]["type"]
            camera_id1 = camera_config1["device"]["id"]
            camera_feature1 = camera_config1["device"]["feature"]

            camera_config2 = camera_config["camera2"]
            camera_type2 = camera_config2["device"]["type"]
            camera_id2 = camera_config2["device"]["id"]
            camera_feature2 = camera_config2["device"]["feature"]

            # Ghi log thông số camera
            self.ui_logger.info(
                f"Khởi tạo camera1: Type={camera_type1}, ID={camera_id1}, Feature={camera_feature1}"
            )
            self.ui_logger.info(
                f"Khởi tạo camera2: Type={camera_type2}, ID={camera_id2}, Feature={camera_feature2}"
            )

            # Khởi tạo camera thread với thông số từ giao diện
            self.init_camera_1(camera_type1, camera_id1, camera_feature1)
            self.init_camera_2(camera_type2, camera_id2, camera_feature2)
            
            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo camera: {str(e)}")
            return False
        
    def init_camera_1(self, camera_type, camera_id, camera_feature):
        if camera_type == "Webcam":
            self.camera1 = CameraThread(
                camera_type, {"id": camera_id, "feature": camera_feature,}
            )
        elif camera_type == "HIK":
            # Cấu hình đặc biệt cho camera HIK nếu cần
            self.camera1 = CameraThread(
                camera_type,
                {
                    "id": camera_id,
                    "feature": f"resources/cameras/HIK/{camera_feature}.ini",
                },
            )
        elif camera_type == "SODA":
            # Cấu hình đặc biệt cho camera SODA nếu cần
            self.camera1 = CameraThread(
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
            self.camera1 = CameraThread("Webcam", {"id": "0", "feature": ""})

    def init_camera_2(self, camera_type, camera_id, camera_feature):
        if camera_type == "Webcam":
            self.camera2 = CameraThread(
                camera_type, {"id": camera_id, "feature": camera_feature,}
            )
        elif camera_type == "HIK":
            # Cấu hình đặc biệt cho camera HIK nếu cần
            self.camera2 = CameraThread(
                camera_type,
                {
                    "id": camera_id,
                    "feature": f"resources/cameras/HIK/{camera_feature}.ini",
                },
            )
        elif camera_type == "SODA":
            # Cấu hình đặc biệt cho camera SODA nếu cần
            self.camera2 = CameraThread(
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
            self.camera2 = CameraThread("Webcam", {"id": "0", "feature": ""})


    def write_log(self):
        """Ghi thử một số log"""
        self.signalLogUI.emit(TypeLog.DEFAULT, "Một thông báo khác")
        self.signalLogUI.emit(TypeLog.DEBUG, "Một thông báo khác")
        self.signalLogUI.emit(TypeLog.INFO, "Một thông báo khác")
        self.signalLogUI.emit(TypeLog.WARNING, "Một thông báo khác")
        self.signalLogUI.emit(TypeLog.ERROR, "Một thông báo khác")
        self.signalLogUI.emit(TypeLog.CRITICAL, "Một thông báo khác")
        # self.ui_logger.debug("Đây là log DEBUG")
        # self.ui_logger.info("Đây là log INFO")
        # self.ui_logger.warning("Đây là log WARNING")
        # self.ui_logger.error("Đây là log ERROR")
        # self.ui_logger.critical("Đây là log CRITICAL")

    def start_elappsed_time(self):
        self.t_start = time.time()

    def get_elappsed_time(self):
        # self.ui_logger.debug(f"Get elappsed_time: {time.time() - self.t_start}")
        return time.time() - self.t_start

    @property
    def b_trigger_weight_auto(self):
        return self._b_trigger_weight_auto

    @b_trigger_weight_auto.setter
    def b_trigger_weight_auto(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_trigger_weight_auto = boolean

    @property
    def b_trigger_optic_auto(self):
        return self._b_trigger_optic_auto

    @b_trigger_optic_auto.setter
    def b_trigger_optic_auto(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_trigger_optic_auto = boolean

    @property
    def b_trigger_unitbox_auto(self):
        return self._b_trigger_unitbox_auto

    @b_trigger_unitbox_auto.setter
    def b_trigger_unitbox_auto(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_trigger_unitbox_auto = boolean

    @property
    def b_stop_auto(self):
        return self._b_stop_auto

    @b_stop_auto.setter
    def b_stop_auto(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_stop_auto = boolean

    @property
    def b_trigger_teaching(self):
        return self._b_trigger_teaching

    @b_trigger_teaching.setter
    def b_trigger_teaching(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_trigger_teaching = boolean

    @property
    def b_stop_teaching(self):
        return self._b_stop_teaching

    @b_stop_teaching.setter
    def b_stop_teaching(self, boolean):
        if not isinstance(boolean, bool):
            raise self.ui_logger.error("Biến phải là kiểu bool!")
        self._b_stop_teaching = boolean

    def on_click_auto_scanner(self):
        """
        Xử lý sự kiện khi nhấn nút Open Auto.
        Hiển thị dialog để chọn cổng COM và test scanner.
        """
        try: 
            # Tạo và hiển thị dialog
            dialog = AutoScannerDlg(self)
            dialog.scannerResult.connect(self.handle_scanner_result)
            
            # Hiển thị dialog và chờ kết quả
            result = dialog.exec_()
            
            # Disconnect signal để tránh memory leak
            dialog.scannerResult.disconnect()
            
        except Exception as e:
            self.ui_logger.error(f"Error in auto scanner: {str(e)}")

    def handle_scanner_result(self, scanned_model):
        """
        Xử lý kết quả từ scanner.
        Kiểm tra xem model đã quét có trong combo_model không.
        """
        try:
            self.ui.label_code_sn.setText(scanned_model)
            self.ui_logger.info(f"Scanned model: {scanned_model}")
            
            # Kiểm tra xem model đã quét có trong danh sách model không
            model_index = self.ui.combo_model.findText(scanned_model)
            
            if model_index >= 0:
                # Model tồn tại, load nó
                self.ui_logger.info(f"Model {scanned_model} load thành công.")
                self.ui.combo_model.setCurrentIndex(model_index)
                
                # Thông báo thành công
                QMessageBox.information(self, "Success", f"Model {scanned_model} load thành công.")
            else:
                # Model không tồn tại, hiển thị cảnh báo
                self.ui_logger.warning(f"Model {scanned_model} không tồn tại.")
                
                reply = QMessageBox.question(
                    self,
                    "Model Not Found",
                    f"Model {scanned_model} không tồn tại trong danh sách. Bạn có muốn tạo model {scanned_model} vào danh sách không?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )                    
                
                if reply == QMessageBox.Yes:
                    # Tạo model mới với tên đã quét
                    success = self.add_model(scanned_model)
                    if success:
                        self.ui_logger.info(f"Model {scanned_model} tạo thành công.")
                        QMessageBox.information(self, "Success", f"Model {scanned_model} tạo thành công.")
                    else:
                        self.ui_logger.error(f"Lỗi khi tạo model {scanned_model}.")
                        QMessageBox.critical(self, "Error", f"Lỗi khi tạo model {scanned_model}.")
        
        except Exception as e:
            self.ui_logger.error(f"Error handling scanner result: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error handling scanner result: {str(e)}")

    def on_click_clear_list(self):
        self.clear_list()

    def clear_list(self, list_widget_code_sn=None):
        self.listCodeSN = []
        if list_widget_code_sn is None:
            list_widget_code_sn = self.ui.list_widget_code_sn

        list_widget_code_sn.clear()
        self.ui.label_count.setText(f"Count: 0")

    def on_click_start(self):
        """
        Xử lý sự kiện khi nhấn nút Start.
        Khởi động luồng auto.
        """
        try:
            self.loadProgress.emit(50, "Start Auto")

            self.ui_logger.info("Bắt đầu khởi động hệ thống Auto")

            self.setup_auto()
            self.start_loop_auto()

            # Cập nhật UI
            self.ui.btn_start.setEnabled(False)
            self.ui.combo_model.setEnabled(False)
            self.ui.btn_stop.setEnabled(True)
            # self.finishProgress.emit()
        except Exception as e:
            self.ui_logger.error(f"Error start auto: {str(e)}")

    def setup_auto(self):
        if self.ui.btn_start_teaching.text() == "Stop Teaching":
            self.stop_teaching()
        if self.ui.btn_start_camera.text() == "Stop":
            self.stop_camera()
            self.close_camera()
        if self.ui.btn_open_camera.text() == "Close":
            self.close_camera()
        if self.ui.btn_open_light.text() == "Close":
            self.close_light()
        if self.ui.btn_open_weight.text() == "Close":
            self.close_weight()
        if self.ui.btn_open_vision_master == "Close":
            self.close_vision_master()
        if self.ui.btn_open_scanner == "Close":
            self.close_scanner()
        if self.ui.btn_open_io.text() == "Close":
            self.close_io()
        if self.ui.btn_connect_server.text() == "Disconnect":
            self.disconnect_server()

        # self.ui.btn_start_teaching.setEnabled(False)
        self.ui.btn_open_camera.setEnabled(False)
        # self.ui.btn_open_light.setEnabled(False)
        # self.ui.btn_open_io.setEnabled(False)
        # self.ui.btn_connect_server.setEnabled(False)

    def on_click_reset(self):
        """
        Xử lý sự kiện khi nhấn nút Reset.
        Dừng tất cả các luồng và thiết lập lại trạng thái.
        """
        try:
            self.ui_logger.info("Đang reset hệ thống")

            # Dừng luồng auto
            self.b_stop_auto = True
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

            # Cập nhật UI
            self.ui.btn_start.setEnabled(True)
            self.ui.combo_model.setEnabled(True)
            self.ui.btn_stop.setEnabled(False)

            self.stop_loop_auto()
            self.release_loop_auto()

            # Khôi phục cấu hình mặc định
            # self.apply_default_config()

        except Exception as e:
            self.ui_logger.error(f"Error reset: {str(e)}")

    def on_click_stop(self):
        """
        Xử lý sự kiện khi nhấn nút Stop.
        Dừng luồng auto.
        """
        try:
            # Cập nhật UI
            self.ui.btn_start.setEnabled(True)
            self.ui.combo_model.setEnabled(True)
            self.ui.btn_stop.setEnabled(False)

            self.stop_loop_auto()
            self.release_loop_auto()

        except Exception as e:
            self.ui_logger.error(f"Error stop auto: {str(e)}")

    def release_loop_auto(self):
        self.io_controller.write_out(OutPorts.Out_1, PortState.Off)  
        time.sleep(0.05)
        self.io_controller.write_out(OutPorts.Out_2, PortState.Off)  
        time.sleep(0.05)
        self.io_controller.write_out(OutPorts.Out_3, PortState.Off)  
        time.sleep(0.05)

        self.clear_list()

        if self.camera1 is not None:
            self.camera1.close_camera()
            self.camera1 = None
        if self.camera2 is not None:
            self.camera2.close_camera()
            self.camera2 = None

        if self.camera_thread is not None:
            self.close_camera()
        if self.light_controller is not None:
            self.close_light()
        if self.weight_controller is not None:
            self.close_weight()
        if self.vision_master_controller is not None:
            self.close_vision_master()
        if self.scanner_controller is not None:
            self.close_scanner()
        if self.out_com_controller is not None:
            self.close_out_com()
        if self.io_controller is not None:
            self.close_io()
        if self.tcp_server is not None:
            self.disconnect_server()
        # self.ui.btn_start_teaching.setEnabled(True)
        self.ui.btn_open_camera.setEnabled(True)
        # self.ui.btn_open_light.setEnabled(True)
        # self.ui.btn_open_io.setEnabled(True)
        # self.ui.btn_connect_server.setEnabled(True)

    def start_loop_auto(self):
        config = self.load_config(model_setting=False)

        # # Init Camera
        # camera_type = config["modules"]["camera"]["type"]
        # camera_id = config["modules"]["camera"]["id"]
        # camera_feature = config["modules"]["camera"]["feature"]
        # self.init_camera(camera_type, camera_id, camera_feature)

        # Init Camera Config
        camera_config = config["modules"]["camera_config"]
        self.init_camera_config(camera_config)

        # Init Lighting
        light_controller_type = config["modules"]["lighting"]["controller_light"]
        com_port_light = config["modules"]["lighting"]["comport_light"]
        baud_rate_light = int(config["modules"]["lighting"]["baudrate_light"])
        self.init_lighting(light_controller_type, com_port_light, baud_rate_light)

        # Init Weight
        com_port_weight = config["modules"]["weight"]["comport_weight"]
        baud_rate_weight = int(config["modules"]["weight"]["baudrate_weight"])
        self.init_weight(com_port_weight, baud_rate_weight)
        min_weight = config["modules"]["weight"]["min_weight"]
        max_weight = config["modules"]["weight"]["max_weight"]
        value_weight = config["modules"]["weight"]["value_weight"]
        self.ui.label_value_min.setText(min_weight)
        self.ui.label_value_max.setText(max_weight)
        self.ui.label_value_weight_auto.setText(value_weight)

        # Init Vision Master
        com_port_vision_master = config["modules"]["vision_master"]["comport_vision_master"]
        baud_rate_vision_master = int(config["modules"]["vision_master"]["baudrate_vision_master"])
        strTrigger = config["modules"]["vision_master"]["string_trigger"]
        self.init_vision_master(com_port_vision_master, baud_rate_vision_master, strTrigger)

        # Init Scanner
        com_port_scanner = config["modules"]["scanner"]["comport_scanner"]
        baud_rate_scanner = int(config["modules"]["scanner"]["baudrate_scanner"])
        self.init_scanner(com_port_scanner, baud_rate_scanner)

        # Init Out COM
        com_port_out_com = config["modules"]["out_com"]["comport_out_com"]
        baud_rate_out_com = int(config["modules"]["out_com"]["baudrate_out_com"])
        self.init_out_com(com_port_out_com, baud_rate_out_com)

        # Init IO Controller
        com_port_io = config["modules"]["io"]["comport_io"]
        baud_rate_io = int(config["modules"]["io"]["baudrate_io"])
        self.init_io(com_port_io, baud_rate_io)

        # Init Server
        host = config["modules"]["server"]["host"]
        port = int(config["modules"]["server"]["port"])
        self.init_server(host, port)

        # Set initial states
        self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
        self.b_trigger_weight_auto = False
        self.b_trigger_optic_auto = False
        self.b_trigger_unitbox_auto = False
        self.b_stop_auto = False
        self.final_result = None

        threading.Thread(target=self.setup_loop_auto, daemon=True).start()

    def setup_loop_auto(self):
        if self.camera1 is not None and self.camera2 is not None:
            t1 = threading.Thread(target=self.open_camera_auto, daemon=True)
            t1.start()
            t1.join()

        time.sleep(0.2)
        if self.light_controller is not None:
            t2 = threading.Thread(target=self.open_light_auto, daemon=True)
            t2.start()
            t2.join()

        time.sleep(0.2)
        if self.weight_controller is not None:
            t3 = threading.Thread(target=self.open_weight_controller_auto, daemon=True)
            t3.start()
            t3.join()

        if self.vision_master_controller is not None:
            t4 = threading.Thread(target=self.open_vision_master_controller_auto, daemon=True)
            t4.start()
            t4.join()

        if self.scanner_controller is not None:
            t5 = threading.Thread(target=self.open_scanner_controller_auto, daemon=True)
            t5.start()
            t5.join()

        if self.out_com_controller is not None:
            t6 = threading.Thread(target=self.open_out_com_controller_auto, daemon=True)
            t6.start()
            t6.join()

        time.sleep(0.2)
        if self.io_controller is not None:
            t7 = threading.Thread(target=self.open_io_controller_auto, daemon=True)
            t7.start()
            t7.join()

        time.sleep(0.2)
        if self.tcp_server is not None:
            t8 = threading.Thread(target=self.connect_server_auto, daemon=True)
            t8.start()
            t8.join()

        time.sleep(0.2)
        threading.Thread(target=self.loop_auto, daemon=True).start()

    def open_camera_auto(self):
        self.camera1.open_camera()
        self.camera2.open_camera()

    def open_light_auto(self):
        self.light_controller.open()
    
    def open_weight_controller_auto(self):
        self.weight_controller.open()
        self.weight_controller.dataReceived.connect(self.wait_weight_received_from_weight_controller)

    def wait_weight_received_from_weight_controller(self, data):
        try:
            # Nếu có tiền tố ST/US
            if ',' in data:
                status, raw_weight = data.split(',', 1)
            else:
                status = 'UNKNOWN'
                raw_weight = data
            
            # Loại bỏ đơn vị (kg, g, ...)
            for unit in ['kg', 'g', 'lb']:
                if unit in raw_weight:
                    raw_weight = raw_weight.replace(unit, '').strip()
                    break
            
            # Loại bỏ dấu + nếu có
            weight = float(raw_weight.replace('+', '').strip())

            self.ui_logger.info(f"[{status}] Trọng lượng: {weight}")

            # Cập nhật giao diện
            self.ui.label_value_weight_auto.setText(f"{weight:.3f}")
            if weight > float(self.ui.label_value_min.text()) and weight < float(self.ui.label_value_max.text()):
                self.ui.label_weight.setProperty("class", "pass")
                update_style(self.ui.label_weight)
            else:
                self.ui.label_weight.setProperty("class", "fail")
                update_style(self.ui.label_weight)
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value weight: {e}")

    def open_vision_master_controller_auto(self):
        self.vision_master_controller.open()
        self.vision_master_controller.dataReceived.connect(self.wait_data_received_from_vision_master_controller)

    def wait_data_received_from_vision_master_controller(self, data):
        try:
            dataVM = [item for item in data.split(";") if len(item) ==  14]
            list_model_code = ';'.join(dataVM)
            self.dataVM = list_model_code
            # self.ui_logger.info(f"Data Vision Master: {self.dataVM}")
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value vision master: {e}")

    def open_scanner_controller_auto(self):
        self.scanner_controller.open()
        self.scanner_controller.dataReceived.connect(self.wait_data_received_from_scanner_controller)

    def wait_data_received_from_scanner_controller(self, data):
        try:
            if data == "Check Weight":
                self.b_trigger_weight_auto = True
            elif data == "Check Optic":
                self.b_trigger_optic_auto = True
            elif data == "Check UnitBox":
                self.b_trigger_unitbox_auto = True
            else:
                if len(data) >=  10:
                    self.listCodeSN.append(data)
                    self.add_list_to_listwidget(self.listCodeSN, list_widget_code_sn=self.ui.list_widget_code_sn)
                # self.ui_logger.info(f"Data Scanner: {self.dataScanner}")
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value scanner: {e}")
    
    def add_list_to_listwidget(self, listCodeSN: List, list_widget_code_sn=None):
        """
        Thêm một list Python có sẵn vào QListWidget.
        
        Args:
            list (list): Danh sách cần thêm vào QListWidget
            list_widget (QListWidget, optional): QListWidget cần thêm vào.
                Nếu None, mặc định sẽ dùng list_widget_code_sn
        
        Returns:
            int: Số lượng phần tử đã thêm vào
        """
        try:
            # Sử dụng list_widget_code_sn nếu không chỉ định list_widget
            if list_widget_code_sn is None:
                list_widget_code_sn = self.ui.list_widget_code_sn

            list_widget_code_sn.clear()
            self.ui_logger.debug(f"List CODE SN: {listCodeSN[-5:][::-1]}")
                
            # Kiểm tra xem đã thêm trùng lặp chưa
            count_added = 0
            
            for item_text in listCodeSN:
                # Chuyển đổi sang chuỗi nếu không phải
                if not isinstance(item_text, str):
                    item_text = str(item_text)
                        
                list_widget_code_sn.insertItem(0, item_text)
                count_added += 1

            for i in range(min(5, list_widget_code_sn.count())):
                list_widget_code_sn.item(i).setForeground(QBrush(QColor(0,0,255)))
                list_widget_code_sn.item(i).setFont(QFont('Arial', 10, QFont.Bold))
                    
            # Cuộn xuống cuối danh sách
            if count_added > 0:
                list_widget_code_sn.scrollToTop()
                
            self.ui.label_count.setText(f"Count: {str(count_added)}")
                
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi thêm listCodeSN vào list_widget_code_sn: {str(e)}")

    def open_out_com_controller_auto(self):
        self.out_com_controller.open()

    def open_io_controller_auto(self):
        self.io_controller.open()
        self.io_controller.write_out(OutPorts.Out_1, PortState.On)
        self.io_controller.inputSignal.connect(
            self.wait_data_received_from_io_controller
        )

    def wait_data_received_from_io_controller(self, commands, states):
        for command, state in zip(commands, states):
            if command == 'In_1' and state == PortState.On:
                self.b_trigger_weight_auto = True
            elif command == 'In_2' and state == PortState.On:
                self.b_trigger_optic_auto = True
            elif command == 'In_3' and state == PortState.On:
                self.b_trigger_unitbox_auto = True

    def connect_server_auto(self):
        self.tcp_server.start()
        self.tcp_server.dataReceived.connect(self.wait_data_received_from_client)

    def wait_data_received_from_client(self, host, address, data):
        if data == "Check Weight":
            self.b_trigger_weight_auto = True
        elif data == "Check Optic":
            self.b_trigger_optic_auto = True
        elif data == "Check UnitBox":
            self.b_trigger_unitbox_auto = True

    def loop_auto(self):
        # Load configuration once at the beginning
        config = self.load_config(model_setting=False)
        if config is None:
            self.ui_logger.error("Failed to load configuration")
            return

        # Initialize model AI only once
        model_path = config["modules"]["model_ai"]["model_path"]
        if not self.init_model_ai(model_path):
            self.ui_logger.error(f"Failed to initialize model AI: {model_path}")
            return

        while True:
            # Cho phép UI cập nhật
            QApplication.processEvents()

            # Kiểm tra nếu đã bị dừng
            if self.b_stop_auto:
                self.ui_logger.debug("Auto thread stopped")
                break

            # Xử lý theo từng bước 
            if self.current_step_auto == STEP_WAIT_TRIGGER_AUTO:
                self.handle_wait_trigger_auto()

            elif self.current_step_auto == STEP_PREPROCESS_WEIGHT_AUTO:
                self.handle_preprocess_weight_auto(config)
            elif self.current_step_auto == STEP_PROCESSING_WEIGHT_AUTO:
                self.handle_processing_weight_auto(config)
            elif self.current_step_auto == STEP_OUTPUT_WEIGHT_AUTO:
                self.handle_output_weight_auto(config)

            elif self.current_step_auto == STEP_PREPROCESS_OPTIC_AUTO:
                self.handle_preprocess_optic_auto(config)
            elif self.current_step_auto == STEP_PROCESSING_OPTIC_AUTO:
                self.handle_processing_optic_auto(config)
            elif self.current_step_auto == STEP_OUTPUT_OPTIC_AUTO:
                self.handle_output_optic_auto(config)

            elif self.current_step_auto == STEP_PREPROCESS_UNITBOX_AUTO:
                self.handle_preprocess_unitbox_auto(config)
            elif self.current_step_auto == STEP_PROCESSING_UNITBOX_AUTO:
                self.handle_processing_unitbox_auto(config)
            elif self.current_step_auto == STEP_OUTPUT_UNITBOX_AUTO:
                self.handle_output_unitbox_auto(config)

            elif self.current_step_auto == STEP_RELEASE_AUTO:
                self.handle_release_auto()

            # Thời gian delay giữa các bước
            time.sleep(0.05)

    def stop_loop_auto(self):
        # Đảm bảo loop auto dừng hoàn toàn
        self.b_stop_auto = True
        self.b_trigger_weight_auto = False
        self.b_trigger_optic_auto = False
        self.b_trigger_unitbox_auto = False
        
        # Hủy bỏ kết quả hiện tại nếu có
        if hasattr(self, 'final_result') and self.final_result is not None:
            self.final_result = None

        self.ui.label_weight.setProperty("class", "waiting")
        update_style(self.ui.label_weight)

        self.ui.label_model_code.setText("Model Code")
        self.ui.label_model_code.setProperty("class", "waiting")
        update_style(self.ui.label_model_code)

    def handle_wait_trigger_auto(self):
        if self.b_trigger_weight_auto:
            self.ui_logger.debug("Step Auto: Wait Trigger Weight")
            self.b_trigger_weight_auto = False
            self.signalChangeLabelResult.emit("Waiting...")

            self.current_step_auto = STEP_PREPROCESS_WEIGHT_AUTO

        if self.b_trigger_optic_auto:
            self.ui_logger.debug("Step Auto: Wait Trigger Optic")
            self.b_trigger_optic_auto = False
            self.signalChangeLabelResult.emit("Waiting...")

            self.current_step_auto = STEP_PREPROCESS_OPTIC_AUTO

        if self.b_trigger_unitbox_auto:
            self.ui_logger.debug("Step Auto: Wait Trigger UnitBox")
            self.b_trigger_unitbox_auto = False
            self.signalChangeLabelResult.emit("Waiting...")

            self.current_step_auto = STEP_PREPROCESS_UNITBOX_AUTO

    def handle_preprocess_weight_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Preprocess Weight")

            type_light = config["modules"]["lighting"]["controller_light"]
            channel_0 = config["modules"]["camera_config"]["camera1"]["lighting"]["channels"][0]
            channel_1 = config["modules"]["camera_config"]["camera1"]["lighting"]["channels"][1]
            channel_2 = config["modules"]["camera_config"]["camera1"]["lighting"]["channels"][2]
            channel_3 = config["modules"]["camera_config"]["camera1"]["lighting"]["channels"][3]
            channels = [channel_0, channel_1, channel_2, channel_3]

            # Mở đèn
            if self.light_controller is not None:
                for i, value in enumerate(channels):
                    if value > 0:
                        if type_light == "LCP":
                            self.light_controller.on_channel(i)
                            self.light_controller.set_light_value(i, value)
                        else:  # DCP controller
                            self.light_controller.on_channel(i, value)

            delay_lighting = config["modules"]["camera_config"]["camera1"]["lighting"]["delay"] / 1000

            time.sleep(delay_lighting)

            # Lấy ảnh hiện tại từ camera
            if self.camera1 is not None:
                self.current_image_camera1 = self.camera1.grab_camera()
                if self.current_image_camera1 is None:
                    self.ui_logger.warning("Image not found")

            # Tắt đèn
            if self.light_controller is not None:
                for i, value in enumerate(channels):
                    if value > 0:
                        self.light_controller.off_channel(i)

            self.current_step_auto = STEP_PROCESSING_WEIGHT_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto preprocess weight time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto preprocess weight error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_processing_weight_auto(self, config):
        try: 
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Processing Weight")
            src = self.current_image_camera1
            
            binary = self.processing_binary(src, config)

            # Ghi lỗi
            self.weight = float(self.ui.label_value_weight_auto.text())
            min_weight = float(config["modules"]["weight"]["min_weight"])
            max_weight = float(config["modules"]["weight"]["max_weight"])
            if self.weight > min_weight and self.weight < max_weight:
                msg = "PASS"
            else:
                if self.weight < min_weight:
                    message = f"Trọng lượng cân nhỏ hơn yêu cầu"
                elif self.weight > max_weight:
                    message = f"Trọng lượng cân lơn hơn yêu cầu"
                comport = config["modules"]["scanner"]["comport_scanner"]
                baudrate = str(config["modules"]["scanner"]["baudrate_scanner"])
            
                self.signalShowPopup.emit(message, comport, baudrate)
                while self.flag_popup:
                    time.sleep(0.01)
                msg = self.popup_result
                self.flag_popup = True

            if len(self.listCodeSN) != 0:
                code_sn = str(self.listCodeSN[-1])
            else: 
                code_sn = "List Code SN is Empty"

            dst = src.copy()

            time_check = time.strftime(DATETIME_FORMAT)
            model_name = self.ui.combo_model.currentText()

            dst = self.put_text_dst(dst, msg, time_check, model_name, code_sn)

            # Tạo kết quả cuối cùng cho auto
            self.final_result = RESULT(
                step="WEIGHT",
                time_check=time.strftime(DATETIME_FORMAT),
                model_name=self.ui.combo_model.currentText(),
                result=msg,
                src=src,
                binary=binary,
                dst=dst,
                code_sn=code_sn,
                weight=str(self.weight),
                error_type=None,
                config=config,
            )

            self.signalResultAuto.emit(self.final_result, "Camera1")

            self.current_step_auto = STEP_OUTPUT_WEIGHT_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto processing weight time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto processing weight error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_output_weight_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Output Weight")

            if self.final_result is not None:
                if self.final_result.result == "PASS":
                    data = self.final_result.code_sn
                    self.out_com_controller.send_data(data)

                self.write_label_result(self.final_result.result) 

                # Ghi log database
                self.write_log_database(self.final_result, config)

            self.current_step_auto = STEP_RELEASE_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto output weight time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto output weight error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_preprocess_optic_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Preprocess Optic")

            type_light = config["modules"]["lighting"]["controller_light"]
            channel_0 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][0]
            channel_1 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][1]
            channel_2 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][2]
            channel_3 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][3]
            channels = [channel_0, channel_1, channel_2, channel_3]

            # Mở đèn
            if self.light_controller is not None:
                for i, value in enumerate(channels):
                    if value > 0:
                        if type_light == "LCP":
                            self.light_controller.on_channel(i)
                            self.light_controller.set_light_value(i, value)
                        else:  # DCP controller
                            self.light_controller.on_channel(i, value)

            delay_lighting = config["modules"]["camera_config"]["camera2"]["lighting"]["delay"] / 1000

            time.sleep(delay_lighting)

            # Lấy ảnh hiện tại từ camera
            if self.camera2 is not None:
                self.current_image_camera2 = self.camera2.grab_camera()
                if self.current_image_camera2 is None:
                    self.ui_logger.warning("Image not found")

            # Tắt đèn
            if self.light_controller is not None:
                for i, value in enumerate(channels):
                    if value > 0:
                        self.light_controller.off_channel(i)

            self.current_step_auto = STEP_PROCESSING_OPTIC_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto preprocess optic time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto preprocess optic error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_processing_optic_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Processing Optic")

            src = self.current_image_camera2

            binary = self.processing_binary(src, config)

            dst = src.copy()

            if len(self.listCodeSN) != 0:
                code_sn = ', '.join(self.listCodeSN[-5:][::-1])
            else: 
                code_sn = "List Code SN is Empty"

            # Thực hiện phát hiện
            results = self.model_ai.detect(src, conf=float(config["modules"]["model_ai"]["confidence"]), imgsz=640)

            
            # Ghi lỗi
            count_empty = 0
            count_optic = 0
            for dnn in results:
                if dnn.class_index == 0:
                    count_empty += 1
                elif dnn.class_index == 1:
                    count_optic += 1
            self.ui.label_value_empty.setText(str(count_empty))
            self.ui.label_value_optic.setText(str(count_optic))
            self.ui.label_value_total.setText(str(count_optic + count_empty))
            if count_optic + count_empty != 5 or count_empty > 0:

                if count_optic < 5:
                    message = f"Số lượng Optic bị thiếu"
                elif count_optic > 5:
                    message = f"Số lượng Optic bị thừa"
                comport = config["modules"]["scanner"]["comport_scanner"]
                baudrate = str(config["modules"]["scanner"]["baudrate_scanner"])
            
                self.signalShowPopup.emit(message, comport, baudrate)
                while self.flag_popup:
                    time.sleep(0.01)
                msg = self.popup_result
                self.flag_popup = True

            elif count_optic == 5:
                msg = "PASS"
                        
            dst = plot_results(results, dst, self.model_ai.label_map, self.model_ai.color_map)

            time_check = time.strftime(DATETIME_FORMAT)
            model_name = self.ui.combo_model.currentText()

            dst = self.put_text_dst(dst, msg, time_check, model_name, code_sn)

            # Tạo kết quả cuối cùng cho auto
            self.final_result = RESULT(
                step="OPTIC",
                time_check=time.strftime(DATETIME_FORMAT),
                model_name=self.ui.combo_model.currentText(),
                result=msg,
                src=src,
                binary=binary,
                dst=dst,
                code_sn=code_sn,
                weight="",
                error_type=None,
                config=config,
            )

            # Phát tín hiệu kết quả auto
            self.signalResultAuto.emit(self.final_result, "Camera2")

            self.current_step_auto = STEP_OUTPUT_OPTIC_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto processing optic time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto processing optic error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_output_optic_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Output Optic")

            if self.final_result is not None:
                self.write_label_result(self.final_result.result) 

                # Ghi log database
                self.write_log_database(self.final_result, config)

            self.current_step_auto = STEP_RELEASE_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto output optic time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto output optic error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_preprocess_unitbox_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Preprocess UnitBox")

            type_light = config["modules"]["lighting"]["controller_light"]
            channel_0 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][0]
            channel_1 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][1]
            channel_2 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][2]
            channel_3 = config["modules"]["camera_config"]["camera2"]["lighting"]["channels"][3]
            channels = [channel_0, channel_1, channel_2, channel_3]

            # Mở đèn
            if self.light_controller is not None:
                for i, value in enumerate(channels):
                    if value > 0:
                        if type_light == "LCP":
                            self.light_controller.on_channel(i)
                            self.light_controller.set_light_value(i, value)
                        else:  # DCP controller
                            self.light_controller.on_channel(i, value)

            delay_lighting = config["modules"]["camera_config"]["camera2"]["lighting"]["delay"] / 1000

            time.sleep(delay_lighting)

            # Lấy ảnh hiện tại từ camera
            if self.camera2 is not None:
                self.current_image_camera2 = self.camera2.grab_camera()
                if self.current_image_camera2 is None:
                        self.ui_logger.warning("Image not found")

            # Tắt đèn
            if self.light_controller is not None:
                for i, value in enumerate(channels):
                    if value > 0:
                        self.light_controller.off_channel(i)

            self.current_step_auto = STEP_PROCESSING_UNITBOX_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto preprocess unitbox time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto preprocess unitbox error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_processing_unitbox_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Processing UnitBox")

            src = self.current_image_camera2
            
            binary = self.processing_binary(src, config)

            if len(self.listCodeSN) != 0:
                code_sn = ', '.join(self.listCodeSN[-5:][::-1])
            else: 
                code_sn = "List Code SN is Empty"

            # Xoá tất cả các file trong thư mục
            for filename in os.listdir(InputBarCodePath):
                file_path = os.path.join(InputBarCodePath, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            if os.path.exists(OutputBarCodePath):
                os.remove(OutputBarCodePath)

            # Giả sử src là ảnh barcode mà bạn đã xử lý
            filename = "BarCode.jpg"  # Thêm đuôi file để đảm bảo có thể mở được
            image_path = os.path.join(InputBarCodePath, filename)

            # Lưu ảnh
            cv.imwrite(image_path, src)

            time.sleep(0.05)
            # Send Trigger Vission Master
            self.vision_master_controller.send_trigger()

            while not os.path.exists(OutputBarCodePath):
                time.sleep(0.01)  # Chờ 100ms rồi kiểm tra lại

            time.sleep(0.05)

            # Ghi lỗi
            parts = self.dataVM.strip().split(";")
            if all(p == parts[0] for p in parts) == True and len(parts) == 5:
                self.ui.label_model_code.setText(parts[0])
                self.ui.label_model_code.setProperty("class", "pass")
                update_style(self.ui.label_model_code)
                msg = "PASS"
            elif all(p == parts[0] for p in parts) == False or len(parts) != 5:
                self.ui.label_model_code.setText("DECODE FAIL")
                self.ui.label_model_code.setProperty("class", "fail")
                update_style(self.ui.label_model_code)

                if all(p == parts[0] for p in parts) == False:
                    message = f"Sai code trong UnitBox"
                elif len(parts) < 5:
                    message = f"Thiếu code trong UnitBox"
                elif len(parts) > 5:
                    message = f"Thừa code trong UnitBox"
                comport = config["modules"]["scanner"]["comport_scanner"]
                baudrate = str(config["modules"]["scanner"]["baudrate_scanner"])
            
                self.signalShowPopup.emit(message, comport, baudrate)
                while self.flag_popup:
                    time.sleep(0.01)
                msg = self.popup_result
                self.flag_popup = True

            dst = cv.imread(OutputBarCodePath)

            time_check = time.strftime(DATETIME_FORMAT)
            model_name = self.ui.combo_model.currentText()

            dst = self.put_text_dst(dst, msg, time_check, model_name, code_sn)
            
            # Tạo kết quả cuối cùng cho auto
            self.final_result = RESULT(
                step="UNITBOX",
                time_check=time.strftime(DATETIME_FORMAT),
                model_name=model_name,
                result=msg,
                src=src,
                binary=binary,
                dst=dst,
                code_sn=code_sn,
                weight="",
                error_type=None,
                config=config,
            )

            # Phát tín hiệu kết quả auto
            self.signalResultAuto.emit(self.final_result, "Camera2")

            self.current_step_auto = STEP_OUTPUT_UNITBOX_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto processing unitbox time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto processing unitbox error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    
    def handle_output_unitbox_auto(self, config):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Output UnitBox")

            if self.final_result is not None:
                self.write_label_result(self.final_result.result)   

                # Ghi log database
                self.write_log_database(self.final_result, config)

            self.current_step_auto = STEP_RELEASE_AUTO
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Auto output unitbox time: {elapsed_time:.3f} seconds")
        except Exception as e:
            self.ui_logger.error(f"Auto output unitbox error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def handle_release_auto(self):
        try:
            self.start_elappsed_time()
            self.ui_logger.debug("Step Auto: Release")

            self.weight = None 

            self.final_result = None

            # Đặt lại trạng thái trigger
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
        except Exception as e:
            self.ui_logger.error(f"Auto release error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_auto = STEP_WAIT_TRIGGER_AUTO
            self.b_trigger_weight_auto = False
            self.b_trigger_optic_auto = False
            self.b_trigger_unitbox_auto = False

    def show_popup(self, message, comport, baudrate):
        try:
            # Create and display dialog
            dialog = PopUpDlg(message=message, comport=comport, baudrate=baudrate)
            
            # Connect scanner data if available
            if self.scanner_controller is not None:
                self.scanner_controller.dataReceived.connect(dialog.wait_data_received_from_scanner_controller)
            
            # Show dialog and wait for result
            result = dialog.popUp()
            print(f"Employee: {dialog.ui.line_mnv.text()}, Result: {result}")

            self.popup_result = result
            self.flag_popup = False
            
        except Exception as e:
            self.ui_logger.error(f"Error showing popup: {str(e)}")

    def handle_confirm_result(self, employee_code, is_pass):
        """
        Handle confirmation result from popup dialog
        """
        try:
            result = "PASS" if is_pass else "FAIL"
            self.ui_logger.info(f"Confirmation from employee {employee_code}: {result}")
                
        except Exception as e:
            self.ui_logger.error(f"Error handling confirmation result: {str(e)}")

    def processing_binary(self, src, config):
        color_type = config["modules"]["processing"]["color"]
        gray = cv.cvtColor(src, ColorType.from_label(color_type).value)

        blur_type = config["modules"]["processing"]["blur"]["type_blur"]
        kernel_blur = config["modules"]["processing"]["blur"]["kernel_size_blur"]
        blur = BlurType.from_label(blur_type).value(gray, (kernel_blur, kernel_blur), 0)

        threshold_type = config["modules"]["processing"]["threshold"]["type_threshold"]
        value_threshold = config["modules"]["processing"]["threshold"]["value_threshold"]
        _, thresh = cv.threshold(blur, value_threshold, 255, ThresholdType.from_label(threshold_type).value)

        morph_type = config["modules"]["processing"]["morphological"]["type_morph"]
        iteration = config["modules"]["processing"]["morphological"]["iteration"]
        kernel_size = config["modules"]["processing"]["morphological"]["kernel_size_morph"]
        kernel = cv.getStructuringElement(cv.MORPH_RECT, (kernel_size, kernel_size))
        binary = cv.morphologyEx(thresh, MorphType.from_label(morph_type).value, kernel, iterations=iteration)
        
        # # Find contours
        # cnts, _ = cv.findContours(
        #     binary, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE
        # )

        # # Draw contours
        # cv.drawContours(dst, cnts, -1, (0, 255, 0), 2)
        return binary
    
    def put_text_dst(self, image, result, time_check, model_name, code_sn):
        if result == "PASS":
            image = cv.putText(image, "OK", (100, 500), cv.FONT_HERSHEY_SIMPLEX, fontScale=10, color=(0, 255, 0), thickness=15, lineType=cv.LINE_AA)
        elif result == "FAIL":
            image = cv.putText(image, "NG", (100, 500), cv.FONT_HERSHEY_SIMPLEX, fontScale=10, color=(0, 0, 255), thickness=15, lineType=cv.LINE_AA)
        image = cv.putText(image, time_check, (100, 2500), cv.FONT_HERSHEY_SIMPLEX, fontScale=3, color=(0, 255, 0), thickness=8, lineType=cv.LINE_4)
        image = cv.putText(image, model_name, (100, 2750), cv.FONT_HERSHEY_SIMPLEX, fontScale=3, color=(0, 255, 0), thickness=8, lineType=cv.LINE_4)
        dst = cv.putText(image, code_sn, (100, 3000), cv.FONT_HERSHEY_SIMPLEX, fontScale=2.5, color=(0, 255, 0), thickness=8, lineType=cv.LINE_4)
        return dst

    def write_label_result(self, result: str):
        print(f"Resutl: {result}")
        if result == "PASS":
            self.signalChangeLabelResult.emit("Pass")
            self.io_controller.write_out(OutPorts.Out_1, PortState.On) 
            time.sleep(0.05)
            self.io_controller.write_out(OutPorts.Out_2, PortState.Off)
            time.sleep(0.05)
            self.io_controller.write_out(OutPorts.Out_3, PortState.Off)
        elif result  == "FAIL": 
            self.signalChangeLabelResult.emit("Fail")
            self.io_controller.write_out(OutPorts.Out_1, PortState.Off) 
            time.sleep(0.05)
            self.io_controller.write_out(OutPorts.Out_2, PortState.On)
            time.sleep(0.05)
            self.io_controller.write_out(OutPorts.Out_3, PortState.Off) 
        else:
            self.signalChangeLabelResult.emit("Wait")
            self.io_controller.write_out(OutPorts.Out_1, PortState.Off) 
            time.sleep(0.05)
            self.io_controller.write_out(OutPorts.Out_2, PortState.Off)
            time.sleep(0.05)
            self.io_controller.write_out(OutPorts.Out_3, PortState.On)

    def write_log_database(self, result: RESULT, config: dict):
        try:
            model_name = result.model_name
            date_now = time.strftime(FOLDER_DATE_FORMAT)

            modules = config["modules"]
            log_dir = modules["system"]["log_dir"]

            try:
                log_size = int(modules["system"]["log_size"]) * 1024
            except:
                log_size = 10 * 1024

            if result is not None:
                os.makedirs(log_dir, exist_ok=True)

                image_folder = os.path.join(log_dir, "images", date_now, model_name, result.step)
                os.makedirs(image_folder, exist_ok=True)

                filename = result.result + "_" + time.strftime(FILENAME_FORMAT)

                image_folder_input = f"{image_folder}\\input"
                os.makedirs(image_folder_input, exist_ok=True)
                image_path_input = os.path.join(image_folder_input, filename.replace(".jpg", "_input.jpg"))
                cv.imwrite(image_path_input, result.src)

                if result.dst is not None:
                    image_folder_output = f"{image_folder}\\output"
                    os.makedirs(image_folder_output, exist_ok=True)
                    image_path_output = os.path.join(image_folder_output, filename.replace(".jpg", "_output.jpg"))
                    cv.imwrite(image_path_output, result.dst)

                threading.Thread(target=self.scan_log_dir, args=(log_dir, log_size), daemon=True).start()

                database_path = os.path.join(log_dir, modules["system"]["database_path"])
                conn = create_db(database_path)

                values = (result.step, result.time_check, result.model_name, result.result, image_path_input, result.code_sn, result.weight, result.error_type)
                sql = "INSERT INTO history (step, time_check, model_name, result, img_path, code_sn, weight, error_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                insert(conn, sql, values)
        except Exception as e:
            self.ui_logger.error(f"Error write log database: {str(e)}")

    def scan_log_dir(self, log_dir, max_size):
        self.ui_logger.debug(f"Scanning log dir '{log_dir}' ...")
        try:
            log_images = os.path.join(log_dir, "images")
            size = scan_dir(log_images)
            if size > max_size:
                if log_images is not None:
                    shutil.rmtree(log_images)
                    self.ui_logger.debug(f"Log dir size > {max_size} --> Remove log dir.")
        except Exception as e:
            self.ui_logger.error(f"Error scan log dir: {str(e)}")

    def on_click_start_teaching(self):
        """
        Xử lý sự kiện khi nhấn nút Start Teaching.
        Khởi động luồng teaching.
        """
        if self.ui.btn_start_teaching.text() == "Start Teaching":
            self.start_teaching()
        else:
            self.stop_teaching()

    def start_teaching(self):
        try:
            self.ui_logger.info("Bắt đầu khởi động hệ thống Teaching")

            # Cập nhật UI
            self.ui.btn_start_teaching.setText("Stop Teaching")
            self.ui.btn_start_teaching.setProperty("class", "danger")
            update_style(self.ui.btn_start_teaching)
            self.ui.combo_model_setting.setEnabled(False)

            # Trigger Teaching
            self.b_trigger_teaching = True

            self.start_loop_teaching()

        except Exception as e:
            self.ui_logger.error(f"Error starting teaching: {str(e)}")

    def stop_teaching(self):
        try:
            self.ui_logger.info("Đang dừng hệ thống Teaching")

            # Cập nhật UI
            self.ui.btn_start_teaching.setText("Start Teaching")
            self.ui.btn_start_teaching.setProperty("class", "success")
            update_style(self.ui.btn_start_teaching)
            self.ui.combo_model_setting.setEnabled(True)

            # Trigger Teaching
            self.b_trigger_teaching = False

            self.stop_loop_teaching()

        except Exception as e:
            self.ui_logger.error(f"Error stopping teaching: {str(e)}")

    def start_loop_teaching(self):
        self.b_stop_teaching = False
        self.current_step_teaching = STEP_WAIT_TRIGGER_TEACHING
        threading.Thread(target=self.loop_teaching, daemon=True).start()

    def loop_teaching(self):
        model_path = self.ui.combo_model_ai.currentText()
        self.init_model_ai(model_path)

        while True:
            # Cho phép UI cập nhật
            QApplication.processEvents()

            # Kiểm tra nếu đã bị dừng
            if self.b_stop_teaching:
                self.ui_logger.info("Teaching thread stopped")
                break

            # Xử lý theo từng bước
            if self.current_step_teaching == STEP_WAIT_TRIGGER_TEACHING:
                self.handle_wait_trigger_teaching()
            elif self.current_step_teaching == STEP_PREPROCESS_TEACHING:
                self.handle_preprocess_teaching()
            elif self.current_step_teaching == STEP_PROCESSING_TEACHING:
                self.handle_processing_teaching()
            elif self.current_step_teaching == STEP_OUTPUT_TEACHING:
                self.handle_output_teaching()
            elif self.current_step_teaching == STEP_RELEASE_TEACHING:
                self.handle_release_teaching()

            # Thời gian delay giữa các bước
            time.sleep(0.05)

    def stop_loop_teaching(self):
        self.b_stop_teaching = True

    def handle_wait_trigger_teaching(self):
        """
        Chờ tín hiệu kích hoạt để bắt đầu chu trình teaching.
        """
        if self.b_trigger_teaching:
            self.ui_logger.debug("Step Teaching: Wait Trigger")
            self.b_trigger_teaching = False
            self.start_elappsed_time()
            self.current_step_teaching = STEP_PREPROCESS_TEACHING

    def handle_preprocess_teaching(self):
        """
        Tiền xử lý ảnh trong chế độ teaching.
        """
        try:
            self.ui_logger.debug("Step Teaching: Preprocess")

            # Lấy ảnh hiện tại từ camera hoặc file
            if self.current_image is None:
                raise Exception("Không có ảnh để xử lý")

            # Kiểm tra ánh sáng
            if self.light_controller is None:
                self.ui_logger.warning("Ánh sáng chưa được mở")

            # Kiem tra Server
            if self.tcp_server is None:
                self.ui_logger.warning("Chưa kết nối tới Server")

            # Chuyển sang bước tiếp theo
            self.current_step_teaching = STEP_PROCESSING_TEACHING

        except Exception as e:
            self.ui_logger.error(f"Teaching preprocessing error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_teaching = STEP_WAIT_TRIGGER_TEACHING
            self.b_trigger_teaching = False

    def handle_processing_teaching(self):
        """
        Xử lý ảnh trong chế độ teaching sử dụng thông số từ giao diện.
        """
        try:
            self.ui_logger.debug("Step Teaching: Processing")

            # Hiển thị kết quả trung gian lên canvas
            if self.current_image is not None:
                src = self.current_image

                color_type = self.ui.combo_color.currentText()
                gray = cv.cvtColor(src, ColorType.from_label(color_type).value)

                blur_type = self.ui.combo_blur.currentText()
                kernel_blur = self.ui.spin_kernel_blur.value()
                if blur_type == "Gaussian Blur":
                    blur = cv.GaussianBlur(gray, (kernel_blur, kernel_blur), 0)
                elif blur_type == "Median Blur":
                    blur = cv.medianBlur(gray, kernel_blur)
                elif blur_type == "Average Blur":
                    blur = cv.blur(gray, (kernel_blur, kernel_blur))

                threshold_type = self.ui.combo_threshold.currentText()
                value_threshold = self.ui.spin_value_threshold.value()
                _, thresh = cv.threshold(blur, value_threshold, 255, ThresholdType.from_label(threshold_type).value)

                morph_type = self.ui.combo_morphological.currentText()
                iteration = self.ui.spin_iteration.value()
                kernel_size = self.ui.spin_kernel_size.value()
                kernel = cv.getStructuringElement(cv.MORPH_RECT, (kernel_size, kernel_size))
                # if morph_type == "Erode":
                #     binary = cv.erode(thresh, kernel, iterations=iteration)
                # elif morph_type == "Dilate":
                #     binary = cv.dilate(thresh, kernel, iterations=iteration)
                binary = cv.morphologyEx(thresh, MorphType.from_label(morph_type).value, kernel, iterations=iteration)

                dst = src.copy()

                # # Find contours
                # cnts, _ = cv.findContours(
                #     binary, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_SIMPLE
                # )

                # # Draw contours
                # cv.drawContours(dst, cnts, -1, (0, 255, 0), 2)
                
                conf = float(self.ui.line_confidence.text())

                if conf < 0.0 or conf > 1.0:
                    conf = 0.25

                # Thực hiện phát hiện
                results = self.model_ai.detect(src, conf=conf, imgsz=640)
                
                # Vẽ kết quả
                dst = plot_results(results, dst, self.model_ai.label_map, self.model_ai.color_map)

                # Tạo kết quả cuối cùng cho teaching
                self.final_result = RESULT(
                    step="Teaching",
                    time_check=time.strftime(DATETIME_FORMAT),
                    model_name=self.ui.combo_model.currentText(),
                    result="",
                    src=src,
                    binary=binary,
                    dst=dst,
                    code_sn="",
                    weight="",
                    error_type=None,
                    config="",
                )

                # Phát tín hiệu kết quả teaching
                self.signalResultTeaching.emit(self.final_result)

            # Chuyển sang bước tiếp theo
            self.current_step_teaching = STEP_OUTPUT_TEACHING

        except Exception as e:
            self.ui_logger.error(f"Teaching processing error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_teaching = STEP_WAIT_TRIGGER_TEACHING
            self.b_trigger_teaching = False

    def handle_output_teaching(self):
        """
        Xuất kết quả và hiển thị kết quả trong chế độ teaching.
        """
        try:
            self.ui_logger.debug("Step Teaching: Output")

            # Thời gian xử lý
            elapsed_time = self.get_elappsed_time()
            self.ui_logger.info(f"Teaching processing time: {elapsed_time:.3f} seconds")

            # Chuyển sang bước tiếp theo
            self.current_step_teaching = STEP_RELEASE_TEACHING

        except Exception as e:
            self.ui_logger.error(f"Teaching output error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step_teaching = STEP_WAIT_TRIGGER_TEACHING
            self.b_trigger_teaching = False

    def handle_release_teaching(self):
        """
        Giải phóng tài nguyên và hoàn tất chu trình teaching.
        """
        try:
            self.ui_logger.debug("Step Teaching: Release")

            # Giải phóng tài nguyên đã khởi tạo
            self.final_result = None

            # Thu hồi bộ nhớ không sử dụng
            gc.collect()

            # Đặt lại trạng thái trigger
            self.b_trigger_teaching = True

            # Chuyển về bước đầu tiên
            self.current_step_teaching = STEP_WAIT_TRIGGER_TEACHING

        except Exception as e:
            self.ui_logger.error(f"Teaching release error: {str(e)}")
            # Trong trường hợp lỗi, vẫn quay lại bước chờ trigger
            self.current_step_teaching = STEP_WAIT_TRIGGER_TEACHING
            self.b_trigger_teaching = False

    def handle_result_auto(self, result, canvas:str):
        """
        Xử lý kết quả từ luồng auto.
        """
        try:
            # Hiển thị ảnh kết quả
            if result.src is not None:
                if canvas == "Camera1":
                    self.canvas_camera1_auto.load_pixmap(ndarray2pixmap(result.src), True)
                elif canvas == "Camera2":
                    self.canvas_camera2_auto.load_pixmap(ndarray2pixmap(result.src), True)

            if result.binary is not None:
                self.canvas_binary.load_pixmap(ndarray2pixmap(result.binary), True)

            if result.dst is not None:
                self.canvas_dst.load_pixmap(ndarray2pixmap(result.dst), True)

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi xử lý kết quả optic auto: {str(e)}")
        finally:
            # Giải phóng bộ nhớ
            gc.collect()

    def handle_result_teaching(self, result):
        """
        Xử lý kết quả từ luồng teaching.
        """
        try:
            self.ui_logger.info(
                f"Nhận kết quả teaching: {result.step}, kết quả: {result.result}"
            )

            # Cập nhật UI với kết quả
            # TODO: Thêm xử lý kết quả teaching

            # Hiển thị ảnh kết quả
            if result.binary is not None:
                self.canvas_binary.load_pixmap(ndarray2pixmap(result.binary))

            if result.dst is not None:
                self.canvas_dst.load_pixmap(ndarray2pixmap(result.dst))

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi xử lý kết quả teaching: {str(e)}")

    def handle_change_label_result(self, text):
        if text == "Wait":
            self.ui.label_result.setProperty("class", "waiting")
            self.ui.label_result.setText("Wait")
            update_style(self.ui.label_result)
        elif text == "Pass":
            self.ui.label_result.setProperty("class", "pass")
            self.ui.label_result.setText("Pass")
            update_style(self.ui.label_result)
        elif text == "Fail":
            self.ui.label_result.setProperty("class", "fail")
            self.ui.label_result.setText("Fail")
            update_style(self.ui.label_result)
        else:
            self.ui.label_result.setProperty("class", "waiting")
            self.ui.label_result.setText("Waiting")
            update_style(self.ui.label_result)

    def handle_log_ui(self, type_log: TypeLog, msg: str):
        timestamp = time.strftime(DATETIME_FORMAT)
        msg = f"{timestamp} : {msg}"
        list_item = QListWidgetItem(msg)

        # Thay đổi màu sắc theo level
        if type_log == TypeLog.DEBUG:
            list_item.setForeground(QColor("blue"))
        elif type_log == TypeLog.INFO:
            list_item.setForeground(QColor("green"))
        elif type_log == TypeLog.WARNING:
            list_item.setForeground(QColor("orange"))
        elif type_log == TypeLog.ERROR:
            list_item.setForeground(QColor("red"))
        elif type_log == TypeLog.CRITICAL:
            list_item.setForeground(QColor("darkred"))
        else:
            list_item

        self.ui.list_widget_log.addItem(list_item)
        self.ui.list_widget_log.scrollToBottom()

    def on_click_refesh(self):
        self.apply_default_config()

    def get_config(self):
        """
        Lấy cấu hình hiện tại của ứng dụng.

        Hàm này thu thập các thông tin cấu hình từ các thành phần khác nhau của ứng dụng
        bao gồm các hình dạng (shapes) trên canvas, các module đã cấu hình,
        và các thiết lập font chữ.

        Returns:
            dict: Từ điển chứa tất cả thông tin cấu hình.
        """
        # Khởi tạo từ điển cấu hình
        config = {}

        # Lưu thông tin về các hình dạng trên canvas
        shapes: list[Shape] = self.canvas_src.shapes
        config["shapes"] = {
            i: {"label": shapes[i].label, "box": shapes[i].cvBox}
            for i in range(len(shapes))
        }

        # Lưu thông tin về các module
        config["modules"] = {}

        # Lưu thiết lập liên quan đến camera

        # config["modules"]["camera_config"] = self.camera_dlg_1.get_config()

        config["modules"]["camera"] = {
            "type": self.ui.combo_type_camera.currentText(),
            "id": self.ui.combo_id_camera.currentText(),
            "feature": self.ui.combo_feature.currentText(),
        }

        # Lưu thiết lập liên quan đến lighting
        config["modules"]["lighting"] = {
            "controller_light": self.ui.combo_controller_light.currentText(),
            "comport_light": self.ui.combo_comport_light.currentText(),
            "baudrate_light": self.ui.combo_baudrate_light.currentText(),
            "delay": self.ui.spin_delay.value(),
            "channels": [
                self.ui.spin_channel_0.value(),
                self.ui.spin_channel_1.value(),
                self.ui.spin_channel_2.value(),
                self.ui.spin_channel_3.value(),
            ],
        }

        # Lưu thiết lập liên quan đến weight
        config["modules"]["weight"] = {
            "comport_weight": self.ui.combo_comport_weight.currentText(),
            "baudrate_weight": self.ui.combo_baudrate_weight.currentText(),
            "min_weight": self.ui.line_min_weight.text(),
            "max_weight": self.ui.line_max_weight.text(),
            "value_weight": self.ui.line_value_weight.text(),
        }

        # Lưu thiết lập liên quan đến vision master
        config["modules"]["vision_master"] = {
            "comport_vision_master": self.ui.combo_comport_vision_master.currentText(),
            "baudrate_vision_master": self.ui.combo_baudrate_vision_master.currentText(),
            "string_trigger": self.ui.line_string_trigger.text(),
        }

        # Lưu thiết lập liên quan đến scanner
        config["modules"]["scanner"] = {
            "comport_scanner": self.ui.combo_comport_scanner.currentText(),
            "baudrate_scanner": self.ui.combo_baudrate_scanner.currentText(),
        }

        # Lưu thiết lập liên quan đến out_com
        config["modules"]["out_com"] = {
            "comport_out_com": self.ui.combo_comport_out_com.currentText(),
            "baudrate_out_com": self.ui.combo_baudrate_out_com.currentText(),
        }

        # Lưu thiết lập liên quan đến io
        config["modules"]["io"] = {
            "comport_io": self.ui.combo_comport_io.currentText(),
            "baudrate_io": self.ui.combo_baudrate_io.currentText(),
        }

        # Lưu thiết lập liên quan đến server
        config["modules"]["server"] = {
            "host": self.ui.line_host_server.text(),
            "port": self.ui.line_port_server.text(),
        }

        # Lưu thiết lập liên quan đến hệ thống
        config["modules"]["system"] = {
            "log_dir": self.ui.line_log_dir.text(),
            "log_size": self.ui.line_log_size.text(),
            "database_path": self.ui.line_database_path.text(),
            "auto_start": self.ui.check_auto_start.isChecked(),
        }

        # Lưu thiết lập liên quan đến model AI
        config["modules"]["model_ai"] = {
            "model_path": self.ui.combo_model_ai.currentText(),
            "confidence": self.ui.line_confidence.text(),
        }

        # Lưu thiết lập liên quan đến processing
        config["modules"]["processing"] = {
            "color": self.ui.combo_color.currentText(),
            "blur": {
                "type_blur": self.ui.combo_blur.currentText(),
                "kernel_size_blur": self.ui.spin_kernel_blur.value(),
            },
            "threshold": {
                "type_threshold": self.ui.combo_threshold.currentText(),
                "value_threshold": self.ui.spin_value_threshold.value(),
            },
            "morphological": {
                "type_morph": self.ui.combo_morphological.currentText(),
                "iteration": self.ui.spin_iteration.value(),
                "kernel_size_morph": self.ui.spin_kernel_size.value(),
            },
        }
        # Lưu thiết lập liên quan đến camera config
        config["modules"]["camera_config"] = {}

        config["modules"]["camera_config"]["camera1"] = self.camera_dlg_1.get_config()
        config["modules"]["camera_config"]["camera2"] = self.camera_dlg_2.get_config()

        # Lưu thiết lập font
        config["font"] = {
            "radius": Shape.RADIUS,
            "thickness": Shape.THICKNESS,
            "font_size": Shape.FONT_SIZE,
            "min_size": Shape.MIN_SIZE,
        }

        # Nếu có file cấu hình font, đọc từ file đó
        if os.path.exists(FONT_CONFIG_PATH):
            with open(FONT_CONFIG_PATH, "r") as f:
                config["font"] = json.load(f)

        # # Ghi nhật ký cấu hình
        # self.ui_logger.debug(
        #     f"Get config: {json.dumps(config, indent=4, ensure_ascii=False)}"
        # )

        return config

    def set_config(self, config):
        """
        Áp dụng cấu hình cho ứng dụng.

        Hàm này nhận một từ điển chứa cấu hình và áp dụng các thiết lập vào
        các thành phần tương ứng trong ứng dụng.

        Args:
            config (dict): Từ điển chứa cấu hình cần áp dụng.
        """
        try:
            # Kiểm tra xem config có hợp lệ không
            if not isinstance(config, dict):
                self.ui_logger.error("Cấu hình không hợp lệ, phải là một từ điển.")
                return

            # # Ghi nhật ký trước khi áp dụng cấu hình
            # self.ui_logger.debug(
            #     f"Setting config: {json.dumps(config, indent=4, ensure_ascii=False)}"
            # )

            # Áp dụng cấu hình shapes nếu có
            if "shapes" in config:
                self.canvas_src.shapes.clear()
                shapes: dict = config["shapes"]
                for i in shapes:
                    label = shapes[i]["label"]
                    x, y, w, h = shapes[i]["box"]
                    s = Shape(label)
                    s.points = [
                        QPointF(x, y),
                        QPointF(x + w, y),
                        QPointF(x + w, y + h),
                        QPointF(x, y + h),
                    ]
                    self.canvas_src.shapes.append(s)

            # Áp dụng cấu hình modules nếu có
            if "modules" in config:
                modules = config["modules"]

                # Áp dụng cấu hình camera
                if "camera" in modules:
                    camera_config = modules["camera"]
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
                if "lighting" in modules:
                    lighting_config = modules["lighting"]
                    self.add_combox_item(self.ui.combo_controller_light, ["LCP", "DCP"])
                    self.set_combobox_text(
                        self.ui.combo_controller_light,
                        lighting_config.get("controller_light", "DCP"),
                    )
                    comports, baudrates = self.find_comports_and_baurates()
                    
                    self.add_combox_item(self.ui.combo_comport_light, comports)
                    self.add_combox_item(self.ui.combo_baudrate_light, baudrates)
                    self.set_combobox_text(
                        self.ui.combo_comport_light,
                        lighting_config.get("comport_light", "COM9"),
                    )
                    self.set_combobox_text(
                        self.ui.combo_baudrate_light,
                        lighting_config.get("baudrate_light", "9600"),
                    )

                    # Đặt giá trị cho spinbox
                    self.ui.spin_delay.setValue(lighting_config.get("delay", 200))

                    # Đặt giá trị cho các kênh
                    channels = lighting_config.get("channels", [10, 10, 10, 10])
                    if len(channels) >= 4:
                        self.ui.spin_channel_0.setValue(channels[0])
                        self.ui.spin_channel_1.setValue(channels[1])
                        self.ui.spin_channel_2.setValue(channels[2])
                        self.ui.spin_channel_3.setValue(channels[3])

                # Áp dụng cấu hình weight
                if "weight" in modules:
                    weight_config = modules["weight"]
                    comports, baudrates = self.find_comports_and_baurates()
                    self.add_combox_item(self.ui.combo_comport_weight, comports)
                    self.add_combox_item(self.ui.combo_baudrate_weight, baudrates)
                    self.set_combobox_text(
                        self.ui.combo_comport_weight, weight_config.get("comport_weight", "COM10")
                    )
                    self.set_combobox_text(
                        self.ui.combo_baudrate_weight, weight_config.get("baudrate_weight", "9600")
                    )
                    self.ui.line_min_weight.setText(str(weight_config.get("min_weight", 0.1)))
                    self.ui.line_max_weight.setText(str(weight_config.get("max_weight", 0.3)))
                    self.ui.line_value_weight.setText(str(weight_config.get("value_weight", 0.2)))
                
                # Áp dụng cấu hình vision master
                if "vision_master" in modules:
                    vision_master_config = modules["vision_master"]
                    comports, baudrates = self.find_comports_and_baurates()
                    self.add_combox_item(self.ui.combo_comport_vision_master, comports)
                    self.add_combox_item(self.ui.combo_baudrate_vision_master, baudrates)
                    self.set_combobox_text(
                        self.ui.combo_comport_vision_master, vision_master_config.get("comport_vision_master", "COM13")
                    )
                    self.set_combobox_text(
                        self.ui.combo_baudrate_vision_master, vision_master_config.get("baudrate_vision_master", "9600")
                    )
                    self.ui.line_string_trigger.setText(str(vision_master_config.get("string_trigger", "TRIGGER")))

                # Áp dụng cấu hình scanner
                if "scanner" in modules:
                    scanner_config = modules["scanner"]
                    comports, baudrates = self.find_comports_and_baurates()
                    self.add_combox_item(self.ui.combo_comport_scanner, comports)
                    self.add_combox_item(self.ui.combo_baudrate_scanner, baudrates)
                    self.set_combobox_text(
                        self.ui.combo_comport_scanner, scanner_config.get("comport_scanner", "COM11")
                    )
                    self.set_combobox_text(
                        self.ui.combo_baudrate_scanner, scanner_config.get("baudrate_scanner", "9600")
                    )

                # Áp dụng cấu hình out_com
                if "out_com" in modules:
                    out_com_config = modules["out_com"]
                    comports, baudrates = self.find_comports_and_baurates()
                    self.add_combox_item(self.ui.combo_comport_out_com, comports)
                    self.add_combox_item(self.ui.combo_baudrate_out_com, baudrates)
                    self.set_combobox_text(
                        self.ui.combo_comport_out_com, out_com_config.get("comport_out_com", "COM16")
                    )
                    self.set_combobox_text(
                        self.ui.combo_baudrate_out_com, out_com_config.get("baudrate_out_com", "9600")
                    )

                # Áp dụng cấu hình io
                if "io" in modules:
                    io_config = modules["io"]
                    comports, baudrates = self.find_comports_and_baurates()
                    self.add_combox_item(self.ui.combo_comport_io, comports)
                    self.add_combox_item(self.ui.combo_baudrate_io, baudrates)
                    self.set_combobox_text(
                        self.ui.combo_comport_io, io_config.get("comport_io", "COM10")
                    )
                    self.set_combobox_text(
                        self.ui.combo_baudrate_io, io_config.get("baudrate_io", "19200")
                    )

                # Áp dụng cấu hình server
                if "server" in modules:
                    server_config = modules["server"]
                    self.ui.line_host_server.setText(
                        server_config.get("host", "127.0.0.1")
                    )
                    self.ui.line_port_server.setText(
                        str(server_config.get("port", 8080))
                    )

                # Áp dụng cấu hình system
                if "system" in modules:
                    system_config = modules["system"]
                    self.ui.line_log_dir.setText(system_config.get("log_dir", "log_database"))
                    self.ui.line_log_size.setText(
                        str(system_config.get("log_size", 10))
                    )
                    self.ui.line_database_path.setText(
                        system_config.get("database_path", "database.db")
                    )
                    self.ui.check_auto_start.setChecked(
                        system_config.get("auto_start", False)
                    )

                # Áp dụng cấu hình module AI
                if "model_ai" in modules:
                    model_ai_config = modules["model_ai"]
                    model_ai = self.find_model_ai()
                    self.add_combox_item(self.ui.combo_model_ai, model_ai)
                    self.set_combobox_text(
                        self.ui.combo_model_ai,
                        model_ai_config.get("model_path", "yolov8n.pt"),
                    )
                    self.ui.line_confidence.setText(
                        str(model_ai_config.get("confidence", 0.25))
                    )

                # Áp dụng cầu hình processing
                if "processing" in modules:
                    processing_config = modules["processing"]
                    list_color = ColorType.list_labels()
                    self.add_combox_item(self.ui.combo_color, list_color)
                    self.set_combobox_text(
                        self.ui.combo_color,
                        processing_config.get("color", "GRAY"),
                    )
                    
                    blur_config = processing_config["blur"]
                    list_blur = BlurType.list_labels()
                    self.add_combox_item(self.ui.combo_blur, list_blur)
                    self.set_combobox_text(
                        self.ui.combo_blur,
                        blur_config.get("type_blur", "Gaussian Blur"),
                    )
                    self.ui.spin_kernel_blur.setRange(1, 101)
                    self.ui.spin_kernel_blur.setSingleStep(2)
                    self.ui.spin_kernel_blur.setValue(blur_config.get("kernel_size_blur", 5))

                    threshold_config = processing_config["threshold"]
                    list_threshold = ThresholdType.list_labels()
                    self.add_combox_item(self.ui.combo_threshold, list_threshold)
                    self.set_combobox_text(
                        self.ui.combo_threshold,
                        threshold_config.get("type_threshold", "Thresh Binary"),
                    )
                    self.ui.spin_value_threshold.setRange(0, 255)
                    self.ui.spin_value_threshold.setValue(threshold_config.get("value_threshold", 127))
                    
                    morphological_config = processing_config["morphological"]
                    list_morph = MorphType.list_labels()
                    self.add_combox_item(self.ui.combo_morphological, list_morph)
                    self.set_combobox_text(
                        self.ui.combo_morphological,
                        morphological_config.get("type_morph", "Erode"),
                    )
                    self.ui.spin_iteration.setRange(0, 50)
                    self.ui.spin_iteration.setValue(morphological_config.get("iteration", 1))
                    self.ui.spin_kernel_size.setRange(1, 101)
                    self.ui.spin_kernel_size.setSingleStep(2)
                    self.ui.spin_kernel_size.setValue(morphological_config.get("kernel_size_morph", 3))

                # Áp dụng cấu hình camera config
                if "camera_config" in modules:
                    camera_config = modules["camera_config"]

                    self.camera_dlg_1.set_config(camera_config["camera1"])
                    self.camera_dlg_2.set_config(camera_config["camera2"])

            # Áp dụng cấu hình font nếu có
            if "font" in config:
                font_config = config["font"]
                Shape.RADIUS = font_config.get("radius", Shape.RADIUS)
                Shape.THICKNESS = font_config.get("thickness", Shape.THICKNESS)
                Shape.FONT_SIZE = font_config.get("font_size", Shape.FONT_SIZE)
                Shape.MIN_SIZE = font_config.get("min_size", Shape.MIN_SIZE)

                # Lưu cấu hình font vào file
                with open(FONT_CONFIG_PATH, "w") as f:
                    json.dump(font_config, f, indent=4)

            self.ui_logger.info("Áp dụng cấu hình thành công.")

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi áp dụng cấu hình: {str(e)}")

    def load_config(self, model_setting=False):
        try:
            if model_setting:
                model_name = self.ui.combo_model_setting.currentText()
            else:
                model_name = self.ui.combo_model.currentText()

            model_path = os.path.join("models", model_name)
            config_path = os.path.join(model_path, "config.json")

            if not os.path.exists(config_path):
                self.ui_logger.info("Không tìm thấy file cấu hình.")
                return

            # Đọc cấu hình từ file
            with open(config_path, "r") as f:
                config = json.load(f)

            self.ui_logger.info("Đọc cấu hình từ file.")

            return config

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi đọc cấu hình: {str(e)}")

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
        type = self.ui.combo_type_camera.currentText()
        self.load_camera_devices(type)

    def find_comports_and_baurates(self):
        comports = serial.tools.list_ports.comports()
        comports = [port for port, _, _ in comports]
        comports.append("COM21")
        comports.append("COM22")

        baudrates = list(map(str, serial.Serial.BAUDRATES))

        return comports, baudrates

    def find_list_client(self):
        if self.tcp_server is not None:
            list_client = self.tcp_server.clients
            return list_client
        return []
    
    def find_model_ai(self):
        model_ai_dir = "resources/models_ai"
        model_names = [name.split('.')[0] for name in os.listdir(model_ai_dir) if name.endswith((".pt", ".pth"))]

        return model_names

    def on_change_model(self):
        """
        Xử lý sự kiện khi thay đổi lựa chọn trong combo_model.
        """
        model_name = self.ui.combo_model.currentText()
        self.load_model(model_name)

    def on_change_model_setting(self):
        """
        Xử lý sự kiện khi thay đổi lựa chọn trong combo_model_setting.
        """
        model_name = self.ui.combo_model_setting.currentText()
        self.load_model(model_name)

    def load_model(self, model_name=None):
        """
        Tải model từ thư mục models/Tên Model.

        Args:
            model_name (str, optional): Tên của model cần tải.
                Nếu None, sẽ lấy model từ combobox model.

        Returns:
            bool: True nếu tải thành công, False nếu thất bại.
        """
        try:
            # Nếu không có tên model được cung cấp, lấy từ combobox
            if model_name is None:
                model_name = self.ui.combo_model_setting.currentText()

            self.ui_logger.info(f"Đang tải model: {model_name}")     

            # Tạo đường dẫn đến file config.json
            model_path = os.path.join("models", model_name)
            config_path = os.path.join(model_path, "config.json")

            # Kiểm tra sự tồn tại của thư mục và file config
            if not os.path.exists(model_path):
                self.ui_logger.error(f"Không tìm thấy thư mục model: {model_path}")
                return False

            if not os.path.exists(config_path):
                self.ui_logger.error(f"Không tìm thấy file cấu hình: {config_path}")
                return False

            # Đọc file config.json
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Áp dụng cấu hình
            self.set_config(config)

            self.ui_logger.info(f"Tải model {model_name} thành công")
            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi tải model {model_name}: {str(e)}")
            return False

    def on_click_add(self):
        self.add_model()

    def add_model(self, model_name=None):
        """
        Thêm một model mới và tải ngay lập tức.

        Args:
            model_name (str, optional): Tên của model mới.
                Nếu None, sẽ hiển thị hộp thoại để nhập tên.

        Returns:
            bool: True nếu thêm thành công, False nếu thất bại.
        """
        try:
            # Nếu không có tên model, hiển thị hộp thoại để nhập tên
            if model_name is None:
                from PyQt5.QtWidgets import QInputDialog

                model_name, ok = QInputDialog.getText(
                    self, "Thêm Model Mới", "Nhập tên model:"
                )
                if not ok or not model_name:
                    self.ui_logger.info("Đã hủy thêm model mới")
                    return False

            # Kiểm tra tên model
            model_name = model_name.strip()
            if not model_name:
                self.ui_logger.error("Tên model không được để trống")
                return False

            # Kiểm tra xem model đã tồn tại chưa
            model_path = os.path.join("models", model_name)
            if os.path.exists(model_path):
                self.ui_logger.error(f"Model {model_name} đã tồn tại")
                return False

            # Tạo thư mục cho model mới
            os.makedirs(model_path, exist_ok=True)

            # Lấy cấu hình hiện tại
            config = self.get_config()

            # Lưu cấu hình vào file config.json
            config_path = os.path.join(model_path, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            # Thêm model vào combobox
            self.ui.combo_model.addItem(model_name)
            self.ui.combo_model_setting.addItem(model_name)

            # Chọn và tải model mới
            self.set_combobox_text(self.ui.combo_model, model_name)
            # self.set_combobox_text(self.ui.combo_model_setting, model_name)

            # Tải model mới (không cần gọi lại vì đã thiết lập currentIndex sẽ trigger on_change_model)
            self.ui_logger.info(f"Đã thêm và tải model mới: {model_name}")
            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi thêm model mới: {str(e)}")
            return False

    def on_click_delete(self):
        self.delete_model()

    def delete_model(self, model_name=None, show_confirm=True):
        """
        Xóa một model.
        Nếu xóa model hiện tại, sẽ tải model khác hoặc áp dụng cấu hình mặc định.

        Args:
            model_name (str, optional): Tên của model cần xóa.
                Nếu None, sẽ xóa model hiện tại được chọn trong combobox.
            show_confirm (bool, optional): Có hiển thị hộp thoại xác nhận không.
                Mặc định là True.

        Returns:
            bool: True nếu xóa thành công, False nếu thất bại.
        """
        try:
            # Nếu không có tên model, lấy từ combobox
            if model_name is None:
                model_name = self.ui.combo_model_setting.currentText()

            # Hiển thị hộp thoại xác nhận nếu cần
            if show_confirm:
                reply = QMessageBox.question(
                    self,
                    "Xác nhận xóa",
                    f"Bạn có chắc chắn muốn xóa model {model_name}?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )

                if reply == QMessageBox.No:
                    self.ui_logger.info("Đã hủy xóa model")
                    return False

            # Kiểm tra đường dẫn model
            model_path = os.path.join("models", model_name)
            if not os.path.exists(model_path):
                self.ui_logger.error(f"Không tìm thấy model: {model_path}")
                return False

            # Xóa thư mục model và tất cả nội dung
            shutil.rmtree(model_path)

            # Xóa model khỏi combobox
            index = self.ui.combo_model.findText(model_name)
            if index >= 0:
                self.ui.combo_model.removeItem(index)

            index = self.ui.combo_model_setting.findText(model_name)
            if index >= 0:
                self.ui.combo_model_setting.removeItem(index)

            # Nếu xóa model hiện tại, cần tải model khác hoặc áp dụng cấu hình mặc định
            self.initialize_models()
                
            self.ui_logger.info(f"Đã xóa model: {model_name}")
            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi xóa model {model_name}: {str(e)}")
            return False


    def on_click_save(self):
        """
        Xử lý sự kiện khi nhấn nút Save.
        Lưu cấu hình hiện tại vào model, nếu tên model thay đổi thì xóa model cũ.
        """
        # Lấy tên model ban đầu và tên model hiện tại (có thể đã được chỉnh sửa)
        original_model_name = self.ui.combo_model_setting.itemText(self.ui.combo_model_setting.currentIndex())
        current_model_name = self.ui.combo_model_setting.currentText()
        
        # Kiểm tra xem tên model có thay đổi không
        if original_model_name != current_model_name and original_model_name:
            # Hỏi người dùng có muốn ghi đè model không
            reply = QMessageBox.question(
                self,
                "Xác nhận đổi tên Model",
                f"Bạn đã đổi tên model từ '{original_model_name}' thành '{current_model_name}'. "
                f"Model '{original_model_name}' sẽ bị xóa. Bạn có muốn tiếp tục?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            
            if reply == QMessageBox.Yes:
                # Lưu model mới
                saved = self.save_model(current_model_name)
                # Xóa model cũ
                self.delete_model(original_model_name, show_confirm=False)
                if saved:
                    # Cập nhật danh sách model
                    if self.ui.combo_model.findText(current_model_name) == -1:
                        self.ui.combo_model.addItem(current_model_name)
                    if self.ui.combo_model_setting.findText(current_model_name) == -1:
                        self.ui.combo_model_setting.addItem(current_model_name)
                    
                    # Chọn model mới
                    self.set_combobox_text(self.ui.combo_model_setting, current_model_name)
                    
                    # Tải model mới
                    self.load_model(current_model_name)
        else:
            # Nếu tên không thay đổi, chỉ cần lưu model
            self.save_model(current_model_name)
            # Tải model để áp dụng các thay đổi
            self.load_model(current_model_name)

    def save_model(self, model_name=None):
        """
        Lưu cấu hình hiện tại vào model.

        Args:
            model_name (str, optional): Tên của model cần lưu.
                Nếu None, sẽ lưu vào model hiện tại được chọn trong combobox.

        Returns:
            bool: True nếu lưu thành công, False nếu thất bại.
        """
        try:
            # Nếu không có tên model, lấy từ combobox
            if model_name is None:
                model_name = self.ui.combo_model_setting.currentText()
            
            # Đảm bảo tên model không trống
            if not model_name.strip():
                self.ui_logger.error("Tên model không được để trống")
                QMessageBox.warning(self, "Lỗi", "Tên model không được để trống")
                return False

            reply = QMessageBox.question(
                self,
                "Xác nhận lưu Model",
                f"Lưu model {model_name}?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.No:
                self.ui_logger.info("Chưa lưu model")
                return False

            # Tạo đường dẫn đến thư mục model
            model_path = os.path.join("models", model_name)

            # Kiểm tra xem model đã tồn tại chưa
            if not os.path.exists(model_path):
                # Tạo thư mục nếu chưa tồn tại
                os.makedirs(model_path, exist_ok=True)
                self.ui_logger.info(f"Đã tạo thư mục model mới: {model_path}")

            # Lấy cấu hình hiện tại
            config = self.get_config()

            # Lưu cấu hình vào file config.json
            config_path = os.path.join(model_path, "config.json")
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.ui_logger.info(f"Đã lưu model {model_name} thành công")
            QMessageBox.information(self, "Thành công", f"Đã lưu model {model_name} thành công")
            return True

        except Exception as e:
            self.ui_logger.error(f"Lỗi khi lưu model {model_name}: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Lỗi khi lưu model {model_name}: {str(e)}")
            return False

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
            # Lấy thông số từ giao diện
            light_controller_type = self.ui.combo_controller_light.currentText()
            comport_light = self.ui.combo_comport_light.currentText()
            baudrate_light = int(self.ui.combo_baudrate_light.currentText())
            self.init_lighting(light_controller_type, comport_light, baudrate_light)

            # Mở kết nối với bộ điều khiển
            status = self.light_controller.open()

            # delay_lighting = self.ui.spin_delay.value() / 1000
            # time.sleep(delay_lighting)

            # Bật các kênh đèn theo giá trị từ giao diện
            channels = [
                self.ui.spin_channel_0.value(),
                self.ui.spin_channel_1.value(),
                self.ui.spin_channel_2.value(),
                self.ui.spin_channel_3.value(),
            ]

            for i, value in enumerate(channels):
                if value > 0:
                    if self.ui.combo_controller_light.currentText() == "LCP":
                        self.light_controller.on_channel(i)
                        self.light_controller.set_light_value(i, value)
                    else:  # DCP controller
                        self.light_controller.on_channel(i, value)
                    self.ui_logger.info(f"Turned on channel {i} with intensity {value}")

            self.ui.btn_open_light.setText("Close")
            self.ui.btn_open_light.setProperty("class", "danger")
            update_style(self.ui.btn_open_light)

            if status:
                self.ui_logger.info("Lighting controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to lighting controller")

        except Exception as e:
            self.ui_logger.error(f"Error Open Light: {e}")

    def close_light(self):
        try:
            # Tắt tất cả các kênh đèn
            channels = [
                self.ui.spin_channel_0.value(),
                self.ui.spin_channel_1.value(),
                self.ui.spin_channel_2.value(),
                self.ui.spin_channel_3.value(),
            ]

            for i, value in enumerate(channels):
                if value > 0:
                    self.light_controller.off_channel(i)
                    self.ui_logger.info(f"Turned off channel {i}")

            # Đóng kết nối với bộ điều khiển
            status = self.light_controller.close()

            self.ui.btn_open_light.setText("Open")
            self.ui.btn_open_light.setProperty("class", "success")
            update_style(self.ui.btn_open_light)

            if status:
                self.ui_logger.info("Lighting controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from lighting controller")

        except Exception as e:
            self.ui_logger.error(f"Error Close Light: {e}")

    def handle_change_light(self, channel_data):
        """
        Handle changes to light intensity values when the controller is open.

        Args:
            channel_data (tuple): A tuple containing (channel_index, intensity_value)
        """
        try:
            channel, value = channel_data

            # Only update light if controller is connected and open
            if self.ui.btn_open_light.text() == "Close":
                self.ui_logger.debug(f"Channel {channel} value changed to {value}")
                if self.ui.combo_controller_light.currentText() == "LCP":
                    if value > 0:
                        self.light_controller.on_channel(channel)
                        self.light_controller.set_light_value(channel, value)
                    elif value == 0:
                        self.light_controller.off_channel(channel)
                else:  # DCP controller
                    if value > 0:
                        self.light_controller.on_channel(channel, value)
                    else:
                        self.light_controller.off_channel(channel)
            else:
                self.ui_logger.debug(f"Light controller not open, change not applied")

        except Exception as e:
            self.ui_logger.error(f"Error handling light change: {str(e)}")

    def on_click_open_scanner(self):
        if self.ui.btn_open_scanner.text() == "Open":
            self.open_scanner()
        else:
            self.close_scanner()

    def open_scanner(self):
        try:
            # Lấy thông số từ giao diện
            comport_scanner = self.ui.combo_comport_scanner.currentText()
            baudrate_scanner = int(self.ui.combo_baudrate_scanner.currentText())
            self.init_scanner(comport_scanner, baudrate_scanner)

            # Mở kết nối với bộ điều khiển
            status = self.scanner_controller.open()

            self.scanner_controller.dataReceived.connect(self.handle_message_scanner)

            self.ui.btn_open_scanner.setText("Close")
            self.ui.btn_open_scanner.setProperty("class", "danger")
            update_style(self.ui.btn_open_scanner)

            if status:
                self.ui_logger.info("Scanner controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to Scanner controller")

        except Exception as e:
            self.ui_logger.error(f"Error Open Scanner: {e}")

    def close_scanner(self):
        try:
            # Đóng kết nối với bộ điều khiển
            status = self.scanner_controller.close()

            self.ui.btn_open_scanner.setText("Open")
            self.ui.btn_open_scanner.setProperty("class", "success")
            update_style(self.ui.btn_open_scanner)

            self.ui.line_message_scanner.setText("")

            if status:
                self.ui_logger.info("Scanner controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from Scanner controller")
        except Exception as e:
            self.ui_logger.error(f"Error Close Scanner: {e}")

    def handle_message_scanner(self, data: str):
        try:
            self.ui.line_message_scanner.setText(data)
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value scanner: {e}")

    def on_click_open_out_com(self):
        if self.ui.btn_open_out_com.text() == "Open":
            self.open_out_com()
        else:
            self.close_out_com()

    def open_out_com(self):
        try:
            # Lấy thông số từ giao diện
            comport_out_com = self.ui.combo_comport_out_com.currentText()
            baudrate_out_com = int(self.ui.combo_baudrate_out_com.currentText())
            self.init_out_com(comport_out_com, baudrate_out_com)

            # Mở kết nối với bộ điều khiển
            status = self.out_com_controller.open()

            self.ui.btn_open_out_com.setText("Close")
            self.ui.btn_open_out_com.setProperty("class", "danger")
            update_style(self.ui.btn_open_out_com)

            if status:
                self.ui_logger.info("Out COM controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to Out COM controller")

        except Exception as e:
            self.ui_logger.error(f"Error Open Out COM: {e}")

    def close_out_com(self):
        try:
            # Đóng kết nối với bộ điều khiển
            status = self.out_com_controller.close()

            self.ui.btn_open_out_com.setText("Open")
            self.ui.btn_open_out_com.setProperty("class", "success")
            update_style(self.ui.btn_open_out_com)

            if status:
                self.ui_logger.info("Out COM controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from Out COM controller")
        except Exception as e:
            self.ui_logger.error(f"Error Close Out COM: {e}")

    def on_click_send_data_out_com(self):
        try:
            data = self.ui.line_data_out_com.text()
            self.out_com_controller.send_data(data)
        except Exception as e:
            self.ui_logger.error(f"Error Send Data Out COM: {e}")

    def on_click_open_io(self):
        if self.ui.btn_open_io.text() == "Open":
            self.open_io()
        else:
            self.close_io()

    def open_io(self):
        try:
            # Lấy thông số từ giao diện
            comport_io = self.ui.combo_comport_io.currentText()
            baudrate_io = int(self.ui.combo_baudrate_io.currentText())
            self.init_io(comport_io, baudrate_io)

            # Mở kết nối với bộ điều khiển
            status = self.io_controller.open()

            # Bật các kênh input theo io
            self.io_controller.inputSignal.connect(self.handle_change_input_io)

            # Bật các kênh output theo io
            self.ui.btn_output_1.setEnabled(True)
            self.ui.btn_output_2.setEnabled(True)
            self.ui.btn_output_3.setEnabled(True)
            self.ui.btn_output_4.setEnabled(True)
            self.ui.btn_output_5.setEnabled(True)
            self.ui.btn_output_6.setEnabled(True)
            self.ui.btn_output_7.setEnabled(True)
            self.ui.btn_output_8.setEnabled(True)

            self.ui.btn_open_io.setText("Close")
            self.ui.btn_open_io.setProperty("class", "danger")
            update_style(self.ui.btn_open_io)

            if status:
                self.ui_logger.info("IO controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to IO controller")

        except Exception as e:
            self.ui_logger.error(f"Error Open IO: {e}")

    def close_io(self):
        try:
            # Đóng kết nối với bộ điều khiển
            # self.on_click_close_all_io()
            status = self.io_controller.close()

            self.ui.btn_output_1.setEnabled(False)
            self.ui.btn_output_2.setEnabled(False)
            self.ui.btn_output_3.setEnabled(False)
            self.ui.btn_output_4.setEnabled(False)
            self.ui.btn_output_5.setEnabled(False)
            self.ui.btn_output_6.setEnabled(False)
            self.ui.btn_output_7.setEnabled(False)
            self.ui.btn_output_8.setEnabled(False)

            self.ui.btn_open_io.setText("Open")
            self.ui.btn_open_io.setProperty("class", "success")
            update_style(self.ui.btn_open_io)

            if status:
                self.ui_logger.info("IO controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from IO controller")
        except Exception as e:
            self.ui_logger.error(f"Error Close IO: {e}")

    def handle_change_input_io(self, commands, states):
        try:
            for command, state in zip(commands, states):
                if command == 'In_1' and state == PortState.On:
                    self.ui.label_input_1.setProperty("class", "pass")
                    self.ui.label_input_1.setText("On")
                    update_style(self.ui.label_input_1)
                if command == 'In_1' and state == PortState.Off:
                    self.ui.label_input_1.setProperty("class", "fail")
                    self.ui.label_input_1.setText("Off")
                    update_style(self.ui.label_input_1)
                if command == 'In_2' and state == PortState.On:
                    self.ui.label_input_2.setProperty("class", "pass")
                    self.ui.label_input_2.setText("On")
                    update_style(self.ui.label_input_2)
                if command == 'In_2' and state == PortState.Off:
                    self.ui.label_input_2.setProperty("class", "fail")
                    self.ui.label_input_2.setText("Off")
                    update_style(self.ui.label_input_2)
                if command == 'In_3' and state == PortState.On:
                    self.ui.label_input_3.setProperty("class", "pass")
                    self.ui.label_input_3.setText("On")
                    update_style(self.ui.label_input_3)
                if command == 'In_3' and state == PortState.Off:
                    self.ui.label_input_3.setProperty("class", "fail")
                    self.ui.label_input_3.setText("Off")
                    update_style(self.ui.label_input_3)
                if command == 'In_4' and state == PortState.On:
                    self.ui.label_input_4.setProperty("class", "pass")
                    self.ui.label_input_4.setText("On")
                    update_style(self.ui.label_input_4)
                if command == 'In_4' and state == PortState.Off:
                    self.ui.label_input_4.setProperty("class", "fail")
                    self.ui.label_input_4.setText("Off")
                    update_style(self.ui.label_input_4)
                if command == 'In_5' and state == PortState.On:
                    self.ui.label_input_5.setProperty("class", "pass")
                    self.ui.label_input_5.setText("On")
                    update_style(self.ui.label_input_5)
                if command == 'In_5' and state == PortState.Off:
                    self.ui.label_input_5.setProperty("class", "fail")
                    self.ui.label_input_5.setText("Off")
                    update_style(self.ui.label_input_5)
                if command == 'In_6' and state == PortState.On:
                    self.ui.label_input_6.setProperty("class", "pass")
                    self.ui.label_input_6.setText("On")
                    update_style(self.ui.label_input_6)
                if command == 'In_6' and state == PortState.Off:
                    self.ui.label_input_6.setProperty("class", "fail")
                    self.ui.label_input_6.setText("Off")
                    update_style(self.ui.label_input_6)
                if command == 'In_7' and state == PortState.On:
                    self.ui.label_input_7.setProperty("class", "pass")
                    self.ui.label_input_7.setText("On")
                    update_style(self.ui.label_input_7)
                if command == 'In_7' and state == PortState.Off:
                    self.ui.label_input_7.setProperty("class", "fail")
                    self.ui.label_input_7.setText("Off")
                    update_style(self.ui.label_input_7)
                if command == 'In_8' and state == PortState.On:
                    self.ui.label_input_8.setProperty("class", "pass")
                    self.ui.label_input_8.setText("On")
                    update_style(self.ui.label_input_8)
                if command == 'In_8' and state == PortState.Off:
                    self.ui.label_input_8.setProperty("class", "fail")
                    self.ui.label_input_8.setText("Off")
                    update_style(self.ui.label_input_8)

        except Exception as e:
            self.ui_logger.error(f"Error handling input change: {str(e)}")

    def on_click_output_1(self):
        if self.ui.btn_output_1.text() == "On":
            self.on_output(self.ui.btn_output_1, OutPorts.Out_1)
        else:
            self.off_output(self.ui.btn_output_1, OutPorts.Out_1)

    def on_click_output_2(self):
        if self.ui.btn_output_2.text() == "On":
            self.on_output(self.ui.btn_output_2, OutPorts.Out_2)
        else:
            self.off_output(self.ui.btn_output_2, OutPorts.Out_2)
    
    def on_click_output_3(self):
        if self.ui.btn_output_3.text() == "On":
            self.on_output(self.ui.btn_output_3, OutPorts.Out_3)
        else:
            self.off_output(self.ui.btn_output_3, OutPorts.Out_3)

    def on_click_output_4(self):
        if self.ui.btn_output_4.text() == "On":
            self.on_output(self.ui.btn_output_4, OutPorts.Out_4)
        else:
            self.off_output(self.ui.btn_output_4, OutPorts.Out_4)
    
    def on_click_output_5(self):
        if self.ui.btn_output_5.text() == "On":
            self.on_output(self.ui.btn_output_5, OutPorts.Out_5)
        else:
            self.off_output(self.ui.btn_output_5, OutPorts.Out_5)

    def on_click_output_6(self):
        if self.ui.btn_output_6.text() == "On":
            self.on_output(self.ui.btn_output_6, OutPorts.Out_6)
        else:
            self.off_output(self.ui.btn_output_6, OutPorts.Out_6)

    def on_click_output_7(self):
        if self.ui.btn_output_7.text() == "On":
            self.on_output(self.ui.btn_output_7, OutPorts.Out_7)
        else:
            self.off_output(self.ui.btn_output_7, OutPorts.Out_7)

    def on_click_output_8(self):
        if self.ui.btn_output_8.text() == "On":
            self.on_output(self.ui.btn_output_8, OutPorts.Out_8)
        else:
            self.off_output(self.ui.btn_output_8, OutPorts.Out_8)

    def on_output(self, button: QPushButton, out: OutPorts):
        self.io_controller.write_out(out, PortState.On)
        button.setText("Off")
        button.setProperty("class", "danger")
        update_style(button)

    def off_output(self, button: QPushButton, out: OutPorts):
        self.io_controller.write_out(out, PortState.Off)
        button.setText("On")
        button.setProperty("class", "success")
        update_style(button)

    def on_click_open_all_io(self):
        self.on_output(self.ui.btn_output_1, OutPorts.Out_1)
        time.sleep(0.5)
        self.on_output(self.ui.btn_output_2, OutPorts.Out_2)
        time.sleep(0.5)
        self.on_output(self.ui.btn_output_3, OutPorts.Out_3)
        time.sleep(0.5)
        self.on_output(self.ui.btn_output_4, OutPorts.Out_4)

    def on_click_close_all_io(self):
        self.off_output(self.ui.btn_output_1, OutPorts.Out_1)
        time.sleep(0.5)
        self.off_output(self.ui.btn_output_2, OutPorts.Out_2)
        time.sleep(0.5)
        self.off_output(self.ui.btn_output_3, OutPorts.Out_3)
        time.sleep(0.5)
        self.off_output(self.ui.btn_output_4, OutPorts.Out_4)

    def on_click_open_weight(self):
        if self.ui.btn_open_weight.text() == "Open":
            self.open_weight()
        else:
            self.close_weight()

    def open_weight(self):
        try:
            # Lấy thông số từ giao diện
            comport_weight = self.ui.combo_comport_weight.currentText()
            baudrate_weight = int(self.ui.combo_baudrate_weight.currentText())
            self.init_weight(comport_weight, baudrate_weight)

            # Mở kết nối với bộ điều khiển
            status = self.weight_controller.open()

            self.weight_controller.dataReceived.connect(self.handle_change_value_weight)

            self.ui.btn_open_weight.setText("Close")
            self.ui.btn_open_weight.setProperty("class", "danger")
            update_style(self.ui.btn_open_weight)

            if status:
                self.ui_logger.info("Weight controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to Weight controller")

        except Exception as e:
            self.ui_logger.error(f"Error Open Weight: {e}")

    def close_weight(self):
        try:
            # Đóng kết nối với bộ điều khiển
            status = self.weight_controller.close()

            self.ui.btn_open_weight.setText("Open")
            self.ui.btn_open_weight.setProperty("class", "success")
            update_style(self.ui.btn_open_weight)

            self.ui.label_value_weight.setProperty("class", "waiting")
            update_style(self.ui.label_value_weight)

            if status:
                self.ui_logger.info("Weight controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from Weight controller")
        except Exception as e:
            self.ui_logger.error(f"Error Close Weight: {e}")

    def handle_change_value_weight(self, data: str):
        try:
            # Nếu có tiền tố ST/US
            if ',' in data:
                status, raw_weight = data.split(',', 1)
            else:
                status = 'UNKNOWN'
                raw_weight = data
            
            # Loại bỏ đơn vị (kg, g, ...)
            for unit in ['kg', 'g', 'lb']:
                if unit in raw_weight:
                    raw_weight = raw_weight.replace(unit, '').strip()
                    break
            
            # Loại bỏ dấu + nếu có
            weight = float(raw_weight.replace('+', '').strip())

            self.ui_logger.info(f"[{status}] Trọng lượng: {weight}")

            # Cập nhật giao diện
            self.ui.line_value_weight.setText(f"{weight:.3f}")
            if weight > float(self.ui.line_min_weight.text()) and weight < float(self.ui.line_max_weight.text()):
                self.ui.label_value_weight.setProperty("class", "pass")
                update_style(self.ui.label_value_weight)
            else:
                self.ui.label_value_weight.setProperty("class", "fail")
                update_style(self.ui.label_value_weight)
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value weight: {e}")

    def on_click_open_vision_master(self):
        if self.ui.btn_open_vision_master.text() == "Open":
            self.open_vision_master()
        else:
            self.close_vision_master()

    def open_vision_master(self):
        try:
            # Lấy thông số từ giao diện
            comport_vision_master = self.ui.combo_comport_vision_master.currentText()
            baudrate_vision_master = int(self.ui.combo_baudrate_vision_master.currentText())
            string_trigger = self.ui.line_string_trigger.text()
            self.init_vision_master(comport_vision_master, baudrate_vision_master, string_trigger)

            # Mở kết nối với bộ điều khiển
            status = self.vision_master_controller.open()

            self.vision_master_controller.dataReceived.connect(self.handle_change_value_vision_master)

            self.ui.btn_open_vision_master.setText("Close")
            self.ui.btn_open_vision_master.setProperty("class", "danger")
            update_style(self.ui.btn_open_vision_master)

            if status:
                self.ui_logger.info("Vision Master connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to Vision Master")

        except Exception as e:
            self.ui_logger.error(f"Error Open Vision Master: {e}")

    def close_vision_master(self):
        try:
            # Đóng kết nối với bộ điều khiển
            status = self.vision_master_controller.close()

            self.ui.btn_open_vision_master.setText("Open")
            self.ui.btn_open_vision_master.setProperty("class", "success")
            update_style(self.ui.btn_open_vision_master)

            if status:
                self.ui_logger.info("Vision Master disconnected successfully")
            else:   
                self.ui_logger.warning("Failed to disconnect from Vision Master")

        except Exception as e:  
            self.ui_logger.error(f"Error Close Vision Master: {e}")

    def handle_change_value_vision_master(self, data: str):
        try:
            dataVM = [item for item in data.split(";") if len(item) ==  14]
            self.ui_logger.debug(f"Vision Master: {dataVM}")
        except Exception as e:
            self.ui_logger.error(f"Lỗi xử lý chuỗi value vision master: {e}")
            
    def on_click_trigger_vision_master(self):
        try:
            self.vision_master_controller.send_trigger()
        except Exception as e:
            self.ui_logger.error(f"Error Trigger Vision Master: {e}")

    def on_click_connect_server(self):
        if self.ui.btn_connect_server.text() == "Connect":
            self.connect_server()
        else:
            self.disconnect_server()

    def connect_server(self):
        try:
            # Lấy thông số từ giao diện
            host = self.ui.line_host_server.text()
            port = int(self.ui.line_port_server.text())
            self.init_server(host, port)
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

            config = self.get_config()
            log_dir = config["modules"]["system"]["log_dir"]
            database_path = os.path.join(log_dir, config["modules"]["system"]["database_path"])

            options = QFileDialog.Options()
            filename,_ = QFileDialog.getOpenFileName(self, "Select file", database_path
                    , "Database files (*.db)", options=options)

            if filename:
                self.database_path = filename
                self.ui_logger.info(f"Connect database success")
                sql = sql = f"SELECT * FROM history"
                conn = create_db(self.database_path)
                rows = select(conn, sql)
                self.update_rows(rows)

            self.ui.btn_connect_database.setText("Disconnect")
            self.ui.btn_connect_database.setProperty("class", "danger")
            update_style(self.ui.btn_connect_database)
        except Exception as e:
            self.ui_logger.error(f"Error Connect Database: {e}")

    def disconnect_database(self):
        try:

            conn = create_db(self.database_path)
            conn.close()
            # self.ui.table_widget_database.clear()
            self.database_path = ""
            self.ui_logger.info(f"Disconnect database success")

            self.ui.btn_connect_database.setText("Connect")
            self.ui.btn_connect_database.setProperty("class", "success")
            update_style(self.ui.btn_connect_database)
        except Exception as e:
            self.ui_logger.error(f"Error Disconnect Database: {e}")

    def create_database(self):
        try:
            config = self.get_config()
            log_dir = config["modules"]["system"]["log_dir"]
            database_path = os.path.join(log_dir, config["modules"]["system"]["database_path"])

            reply = QMessageBox.question(
                self,
                f"Tạo Database",
                f"Xác nhận tạo Database: {config["modules"]["system"]["database_path"]}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.No:
                self.ui_logger.info("Chưa tạo database")
                return False

            os.makedirs(os.path.dirname(database_path), exist_ok=True)
            with open("resources/database/database.sql", "r") as file:
                sql_script = file.read()
                conn = create_db(database_path)
                conn.executescript(sql_script)
        except Exception as e:
            self.ui_logger.error(f"Error Create Database: {e}")

    def on_item_table_data_selection_changed(self):
        row = self.ui.table_widget_database.currentRow()
        it = self.ui.table_widget_database.item(row, IMAGE_PATH_COLUMN)

        if it is not None:
            img_path_input = it.text()

            if not os.path.exists(img_path_input):
                self.ui_logger.error("File not found %s" % img_path_input)
                self.canvas_input.clear_pixmap()
            else:
                src = cv.imread(img_path_input)
                self.canvas_input.load_pixmap(ndarray2pixmap(src), True)

            dirname = Path(Path(img_path_input).parent).parent
            basename = Path(img_path_input).name

            img_path_output = os.path.join(dirname, "output", basename.replace("_input.jpg", "_output.jpg"))
            if not os.path.exists(img_path_output):
                self.ui_logger.error("File not found %s" % img_path_output)
                self.canvas_output.clear_pixmap()
            else:
                dst = cv.imread(img_path_output)
                self.canvas_output.load_pixmap(ndarray2pixmap(dst), True)

    def filter_data(self):
        if self.database_path != "":
            date_from = self.ui.date_time_from.dateTime().toString("yyyy/MM/dd hh:mm:ss")
            date_to = self.ui.date_time_to.dateTime().toString("yyyy/MM/dd hh:mm:ss")

            step = self.ui.combo_step.currentText()
            if step == "ALL":
                step = ""
            
            result = self.ui.combo_result_type.currentText()
            if result == "ALL":
                result = ""

            error_type = self.ui.combo_error_type.currentText()
            if error_type == "All":
                error_type = ""

            key_word = self.ui.line_keyword.text()

            sql = f"SELECT step,time_check,model_name,result,img_path,code_sn,weight,error_type FROM history WHERE \
                    (time_check BETWEEN '{date_from}' AND '{date_to}') \
                    AND (step LIKE '%{step}%') \
                    AND (result LIKE '%{result}%') \
                    AND (time_check LIKE '%{key_word}%' OR model_name LIKE '%{key_word}%' OR result LIKE '%{key_word}%' OR code_sn LIKE '%{key_word}%' OR weight LIKE '%{key_word}%' OR img_path LIKE '%{key_word}%' OR error_type LIKE '%{key_word}%') \
                    "
                    # AND (error_type LIKE '%{error_type}%') \
            conn = create_db(self.database_path)
            rows = select(conn, sql)
            self.update_rows(rows)

    def update_rows(self, rows):
        self.ui.table_widget_database.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j in range(len(r)):
                self.ui.table_widget_database.setItem(i, j, QTableWidgetItem(r[j]))

    def export_to_excel(self):
        try: 
            path, _ = QFileDialog.getSaveFileName(self, "Lưu file Excel", "", "Excel Files (*.xlsx)")
            if path:
                data = []
                for row in range(self.ui.table_widget_database.rowCount()):
                    row_data = []
                    for col in range(self.ui.table_widget_database.columnCount()):
                        item = self.ui.table_widget_database.item(row, col)
                        value = item.text() if item else ""
                        
                        row_data.append(value)
                    data.append(row_data)

                headers = [self.ui.table_widget_database.horizontalHeaderItem(i).text() 
                        for i in range(self.ui.table_widget_database.columnCount())]
                
                df = pd.DataFrame(data, columns=headers)
                df.to_excel(path, index=False, engine='xlsxwriter')

        except Exception as e:
            self.ui_logger.error(f"Error Export To Excel: {e}")

    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, 
            'Confirm Exit', 
            'Are you sure you want to exit?',
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # User chose Yes - accept the close event and exit
            # First do cleanup
            if hasattr(self, 'camera_thread') and self.camera_thread is not None:
                self.camera_thread.stop_camera()
                self.camera_thread.wait()  # Wait for thread to finish

            if self.ui.btn_start.isEnabled() == False:
                self.on_click_stop()

            self.ui_logger.info("Exit")
                
            event.accept()
        else:
            # User chose No - ignore the close event and continue
            event.ignore()

if __name__ == "__main__":
    window = MainWindow()
    window.showMaximized()
    window.setWindowTitle("Project Name")
    window.setWindowIcon(QIcon("resources/icons/cyber-eye.png"))
    load_style_sheet("resources/themes/light_theme.qss", QApplication.instance())
    window.show()
    sys.exit(app.exec_())
