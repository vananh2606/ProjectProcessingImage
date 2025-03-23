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

class AutoThread(threading.Thread):
    """
    Thread chạy vòng lặp tự động theo model đã lưu.
    """
    def __init__(self, window):
        super(AutoThread, self).__init__()
        self.window = window
        self.daemon = True  # Thread sẽ tự động kết thúc khi chương trình chính kết thúc
        self.current_step = STEP_WAIT_TRIGGER
        
    def run(self):
        """
        Thực hiện vòng lặp chính cho auto mode.
        """
        self.window.ui_logger.info("Auto thread started")
        
        while True:
            # Kiểm tra nếu đã bị dừng
            if self.window.b_stop_auto:
                self.window.ui_logger.info("Auto thread stopped")
                break
            
            # Xử lý theo từng bước
            if self.current_step == STEP_WAIT_TRIGGER:
                self.handle_wait_trigger()
            elif self.current_step == STEP_PREPROCESS:
                self.handle_preprocess()
            elif self.current_step == STEP_PROCESSING:
                self.handle_processing()
            elif self.current_step == STEP_OUTPUT:
                self.handle_output()
            elif self.current_step == STEP_RELEASE:
                self.handle_release()
            
            # Thời gian delay giữa các bước
            time.sleep(0.01)
    
    def handle_wait_trigger(self):
        """
        Chờ tín hiệu kích hoạt để bắt đầu chu trình.
        """
        if self.window.b_trigger_auto:
            self.window.ui_logger.info("Auto trigger detected")
            # Lấy thời gian bắt đầu
            self.window.start_elappsed_time()
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_PREPROCESS
    
    def handle_preprocess(self):
        """
        Tiền xử lý ảnh từ camera hoặc file.
        """
        try:
            self.window.ui_logger.info("Auto preprocessing started")
            
            # Lấy ảnh hiện tại
            if self.window.current_image is None:
                # Thử lấy ảnh từ camera nếu không có ảnh
                if self.window.camera_thread and self.window.camera_thread.is_opened():
                    self.window.current_image = self.window.camera_thread.grab_camera()
                    if self.window.current_image is None:
                        raise Exception("Không thể lấy ảnh từ camera")
                else:
                    raise Exception("Không có ảnh và camera không được mở")
            
            # Lấy thông số ánh sáng từ model hiện tại
            lighting_config = self.window.get_config()["modules"]["lighting"]
            channels = lighting_config.get("channels", [10, 10, 10, 10])
            
            # Kích hoạt ánh sáng theo cấu hình
            if self.window.light_controller:
                for i, value in enumerate(channels):
                    if value > 0:
                        self.window.light_controller.on_channel(i, value)
                        self.window.ui_logger.debug(f"Auto: Turned on channel {i} with intensity {value}")
            
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_PROCESSING
            self.window.ui_logger.info("Auto preprocessing completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Auto preprocessing error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_auto = False
    
    def handle_processing(self):
        """
        Xử lý ảnh theo thuật toán của model.
        """
        try:
            self.window.ui_logger.info("Auto processing started")
            
            # TODO: Thêm mã xử lý ảnh và logic thuật toán ở đây
            # Ví dụ:
            # 1. Chuyển đổi ảnh theo chế độ (RGB/HSV) từ config
            # 2. Áp dụng các phép biến đổi
            # 3. Thực hiện phân tích, nhận dạng, v.v.
            
            # Hiển thị kết quả trung gian lên canvas 
            if self.window.current_image is not None:
                # Ví dụ: Hiển thị ảnh nhị phân
                binary_image = self.create_binary_image(self.window.current_image) 
                self.window.canvas_binary.load_pixmap(ndarray2pixmap(binary_image))
            
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_OUTPUT
            self.window.ui_logger.info("Auto processing completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Auto processing error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_auto = False
    
    def handle_output(self):
        """
        Xuất kết quả và hiển thị kết quả.
        """
        try:
            self.window.ui_logger.info("Auto output started")
            
            # Thời gian xử lý
            elapsed_time = self.window.get_elappsed_time()
            self.window.ui_logger.info(f"Auto processing time: {elapsed_time:.3f} seconds")
            
            # TODO: Thêm mã xử lý kết quả và hiển thị
            # Ví dụ: Cập nhật UI, hiển thị kết quả Pass/Fail, v.v.
            
            # Tạo kết quả cuối cùng
            self.window.final_result = RESULT(
                camera=self.window.ui.combo_type_camera.currentText(),
                model=self.window.ui.combo_model.currentText(),
                code="AUTO-" + time.strftime("%Y%m%d-%H%M%S"),
                src=self.window.current_image.copy(),
                dst=self.window.current_image.copy(),  # Thay bằng ảnh đã xử lý
                bin=self.window.current_image.copy(),  # Thay bằng ảnh nhị phân thực tế
                result="OK",  # Thay bằng kết quả thực tế (OK/NG)
                time_check=elapsed_time,
                error_type=None,  # Nếu có lỗi, ghi loại lỗi ở đây
                config=self.window.get_config()
            )
            
            # Phát tín hiệu kết quả
            self.window.signalResultAuto.emit(self.window.final_result)
            
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_RELEASE
            self.window.ui_logger.info("Auto output completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Auto output error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_auto = False
    
    def handle_release(self):
        """
        Giải phóng tài nguyên và hoàn tất chu trình.
        """
        try:
            self.window.ui_logger.info("Auto release started")
            
            # Tắt đèn nếu cần
            if self.window.light_controller:
                for i in range(4):  # Tắt tất cả 4 kênh
                    self.window.light_controller.off_channel(i)
                    self.window.ui_logger.debug(f"Auto: Turned off channel {i}")
            
            # Đặt lại trạng thái trigger
            self.window.b_trigger_auto = False
            
            # Chuyển về bước đầu tiên
            self.current_step = STEP_WAIT_TRIGGER
            self.window.ui_logger.info("Auto release completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Auto release error: {str(e)}")
            # Trong trường hợp lỗi, vẫn quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_auto = False
    
    def create_binary_image(self, image):
        """
        Tạo ảnh nhị phân từ ảnh gốc (ví dụ).
        """
        try:
            # Chuyển sang ảnh xám
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
            # Làm mờ ảnh để giảm nhiễu
            blur = cv.GaussianBlur(gray, (5, 5), 0)
            # Nhị phân hóa bằng ngưỡng Otsu
            _, binary = cv.threshold(blur, 0, 255, cv.THRESH_BINARY)
            return binary
        except Exception as e:
            self.window.ui_logger.error(f"Error creating binary image: {str(e)}")
            return image  # Trả về ảnh gốc trong trường hợp lỗi


class TeachingThread(threading.Thread):
    """
    Thread chạy vòng lặp teaching theo thông số từ giao diện.
    """
    def __init__(self, window):
        super(TeachingThread, self).__init__()
        self.window = window
        self.daemon = True  # Thread sẽ tự động kết thúc khi chương trình chính kết thúc
        self.current_step = STEP_WAIT_TRIGGER
        
    def run(self):
        """
        Thực hiện vòng lặp chính cho teaching mode.
        """
        self.window.ui_logger.info("Teaching thread started")
        
        while True:
            # Kiểm tra nếu đã bị dừng
            if self.window.b_stop_teaching:
                self.window.ui_logger.info("Teaching thread stopped")
                break
            
            # Xử lý theo từng bước
            if self.current_step == STEP_WAIT_TRIGGER:
                self.handle_wait_trigger()
            elif self.current_step == STEP_PREPROCESS:
                self.handle_preprocess()
            elif self.current_step == STEP_PROCESSING:
                self.handle_processing()
            elif self.current_step == STEP_OUTPUT:
                self.handle_output()
            elif self.current_step == STEP_RELEASE:
                self.handle_release()
            
            # Thời gian delay giữa các bước
            time.sleep(0.01)
    
    def handle_wait_trigger(self):
        """
        Chờ tín hiệu kích hoạt để bắt đầu chu trình teaching.
        """
        if self.window.b_trigger_teaching:
            self.window.ui_logger.info("Teaching trigger detected")
            # Lấy thời gian bắt đầu
            self.window.start_elappsed_time()
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_PREPROCESS
    
    def handle_preprocess(self):
        """
        Tiền xử lý ảnh trong chế độ teaching.
        """
        try:
            self.window.ui_logger.info("Teaching preprocessing started")
            
            # Lấy ảnh hiện tại
            if self.window.current_image is None:
                # Thử lấy ảnh từ camera nếu không có ảnh
                if self.window.camera_thread and self.window.camera_thread.is_opened():
                    self.window.current_image = self.window.camera_thread.grab_camera()
                    if self.window.current_image is None:
                        raise Exception("Không thể lấy ảnh từ camera")
                else:
                    raise Exception("Không có ảnh và camera không được mở")
            
            # Lấy thông số ánh sáng trực tiếp từ giao diện
            channels = [
                self.window.ui.spin_channel_0.value(),
                self.window.ui.spin_channel_1.value(),
                self.window.ui.spin_channel_2.value(),
                self.window.ui.spin_channel_3.value()
            ]
            
            # Kích hoạt ánh sáng theo cấu hình giao diện
            if self.window.light_controller:
                for i, value in enumerate(channels):
                    if value > 0:
                        self.window.light_controller.on_channel(i, value)
                        self.window.ui_logger.debug(f"Teaching: Turned on channel {i} with intensity {value}")
            
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_PROCESSING
            self.window.ui_logger.info("Teaching preprocessing completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Teaching preprocessing error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_teaching = False
    
    def handle_processing(self):
        """
        Xử lý ảnh trong chế độ teaching sử dụng thông số từ giao diện.
        """
        try:
            self.window.ui_logger.info("Teaching processing started")
            
            # Lấy thông số từ giao diện
            camera_type = self.window.ui.combo_type_camera.currentText()
            camera_id = self.window.ui.combo_id_camera.currentText()
            camera_feature = self.window.ui.combo_feature.currentText()
            
            # TODO: Thêm mã xử lý ảnh theo thông số từ giao diện
            # Ví dụ:
            # 1. Chuyển đổi ảnh theo chế độ (RGB/HSV) từ UI
            # 2. Áp dụng các phép biến đổi với thông số từ UI
            # 3. Thực hiện phân tích, nhận dạng, v.v.
            
            # Hiển thị kết quả trung gian lên canvas
            if self.window.current_image is not None:
                # Ví dụ: Hiển thị ảnh nhị phân
                binary_image = self.create_binary_image(self.window.current_image)
                self.window.canvas_binary.load_pixmap(ndarray2pixmap(binary_image))
            
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_OUTPUT
            self.window.ui_logger.info("Teaching processing completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Teaching processing error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_teaching = False
    
    def handle_output(self):
        """
        Xuất kết quả và hiển thị kết quả trong chế độ teaching.
        """
        try:
            self.window.ui_logger.info("Teaching output started")
            
            # Thời gian xử lý
            elapsed_time = self.window.get_elappsed_time()
            self.window.ui_logger.info(f"Teaching processing time: {elapsed_time:.3f} seconds")
            
            # TODO: Thêm mã xử lý kết quả và hiển thị
            # Ví dụ: Cập nhật UI, hiển thị kết quả, v.v.
            
            # Tạo kết quả cuối cùng cho teaching
            self.window.final_result = RESULT(
                camera=self.window.ui.combo_type_camera.currentText(),
                model="TEACHING",  # Chế độ teaching không sử dụng model
                code="TEACH-" + time.strftime("%Y%m%d-%H%M%S"),
                src=self.window.current_image.copy(),
                dst=self.window.current_image.copy(),  # Thay bằng ảnh đã xử lý
                bin=self.window.current_image.copy(),  # Thay bằng ảnh nhị phân thực tế
                result="OK",  # Thay bằng kết quả thực tế (OK/NG)
                time_check=elapsed_time,
                error_type=None,  # Nếu có lỗi, ghi loại lỗi ở đây
                config=self.window.get_config()  # Config hiện tại từ UI
            )
            
            # Phát tín hiệu kết quả teaching
            self.window.signalResultTeaching.emit(self.window.final_result)
            
            # Chuyển sang bước tiếp theo
            self.current_step = STEP_RELEASE
            self.window.ui_logger.info("Teaching output completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Teaching output error: {str(e)}")
            # Trong trường hợp lỗi, quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_teaching = False
    
    def handle_release(self):
        """
        Giải phóng tài nguyên và hoàn tất chu trình teaching.
        """
        try:
            self.window.ui_logger.info("Teaching release started")
            
            # Tắt đèn nếu cần
            if self.window.light_controller:
                for i in range(4):  # Tắt tất cả 4 kênh
                    self.window.light_controller.off_channel(i)
                    self.window.ui_logger.debug(f"Teaching: Turned off channel {i}")
            
            # Đặt lại trạng thái trigger
            self.window.b_trigger_teaching = False
            
            # Chuyển về bước đầu tiên
            self.current_step = STEP_WAIT_TRIGGER
            self.window.ui_logger.info("Teaching release completed")
            
        except Exception as e:
            self.window.ui_logger.error(f"Teaching release error: {str(e)}")
            # Trong trường hợp lỗi, vẫn quay lại bước chờ trigger
            self.current_step = STEP_WAIT_TRIGGER
            self.window.b_trigger_teaching = False
    
    def create_binary_image(self, image):
        """
        Tạo ảnh nhị phân từ ảnh gốc (ví dụ).
        """
        try:
            # Chuyển sang ảnh xám
            gray = cv.cvtColor(image, cv.COLOR_BGR2GRAY)
            # Làm mờ ảnh để giảm nhiễu
            blur = cv.GaussianBlur(gray, (5, 5), 0)
            # Nhị phân hóa bằng ngưỡng Otsu
            _, binary = cv.threshold(blur, 0, 255, cv.THRESH_BINARY)
            return binary
        except Exception as e:
            self.window.ui_logger.error(f"Error creating binary image: {str(e)}")
            return image  # Trả về ảnh gốc trong trường hợp lỗi


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
        self.tcp_server = None

        # Camera
        self.camera_thread = None

        # Image
        self.current_image = None
        self.file_paths = []

        # Lighting
        self.light_controller = None

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

        # Model
        self.initialize_models()
        self.init_all_modules()

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

        # Kết nối tín hiệu kết quả
        self.signalResultAuto.connect(self.handle_result_auto)
        self.signalResultTeaching.connect(self.handle_result_teaching)

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
            model_dirs = [d for d in os.listdir("models") 
                        if os.path.isdir(os.path.join("models", d))]
            
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
                self.ui_logger.warning("Không tìm thấy model nào, áp dụng cấu hình mặc định")
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
                        "feature": "RGB"
                    },
                    "lighting": {
                        "controller": "LCP",
                        "com": "COM9",
                        "baudrate": "19200",
                        "delay": 100,
                        "channels": [10, 10, 10, 10]
                    },
                    "server": {
                        "host": "127.0.0.1",
                        "port": "8080"
                    },
                    "system": {
                        "log_dir": "logs",
                        "log_size": "1.0",
                        "database_path": "database.db",
                        "auto_start": False
                    }
                },
                "font": {
                    "radius": Shape.RADIUS,
                    "thickness": Shape.THICKNESS,
                    "font_size": Shape.FONT_SIZE,
                    "min_size": Shape.MIN_SIZE
                }
            }
            
            # Áp dụng cấu hình mặc định
            self.set_config(default_config)
            self.ui_logger.info("Đã áp dụng cấu hình mặc định")
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi áp dụng cấu hình mặc định: {str(e)}")

    def init_camera(self):
        """
        Khởi tạo camera với thông số từ giao diện.
        """
        try:
            # Lấy thông số từ giao diện
            camera_type = self.ui.combo_type_camera.currentText()
            camera_id = self.ui.combo_id_camera.currentText() 
            camera_feature = self.ui.combo_feature.currentText()
            
            # Ghi log thông số camera
            self.ui_logger.info(f"Khởi tạo camera: Type={camera_type}, ID={camera_id}, Feature={camera_feature}")
            
            # Khởi tạo camera thread với thông số từ giao diện
            if camera_type == "Webcam":
                self.camera_thread = CameraThread(camera_type, {"id": camera_id, "feature": camera_feature})
            elif camera_type == "HIK":
                # Cấu hình đặc biệt cho camera HIK nếu cần
                self.camera_thread = CameraThread(camera_type, {"id": camera_id, "feature": camera_feature})
            elif camera_type == "SODA":
                # Cấu hình đặc biệt cho camera SODA nếu cần
                self.camera_thread = CameraThread(camera_type, {"id": camera_id, "feature": camera_feature})
            else:
                # Mặc định sử dụng Webcam
                self.ui_logger.warning(f"Loại camera {camera_type} không được hỗ trợ, sử dụng Webcam mặc định")
                self.camera_thread = CameraThread("Webcam", {"id": "0", "feature": ""})
                
            return True
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo camera: {str(e)}")
            return False

    def init_lighting(self):
        """
        Khởi tạo bộ điều khiển đèn với thông số từ giao diện.
        """
        try:
            # Lấy thông số từ giao diện
            controller_type = self.ui.combo_controller.currentText()
            com_port = self.ui.combo_comport.currentText()
            baud_rate = int(self.ui.combo_baudrate.currentText())
            
            # Ghi log thông số lighting
            self.ui_logger.info(f"Khởi tạo lighting: Type={controller_type}, COM={com_port}, Baud={baud_rate}")
            
            # Khởi tạo bộ điều khiển đèn với thông số từ giao diện
            if controller_type == "LCP":
                self.light_controller = LCPController(com=com_port, baud=baud_rate)
            elif controller_type == "DCP":
                self.light_controller = DCPController(com=com_port, baud=baud_rate)
            else:
                # Mặc định sử dụng DCP
                self.ui_logger.warning(f"Loại bộ điều khiển {controller_type} không được hỗ trợ, sử dụng DCP mặc định")
                self.light_controller = DCPController(com=com_port, baud=baud_rate)
                
            return True
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi tạo lighting: {str(e)}")
            return False

    def init_server(self):
        """
        Khởi tạo server với thông số từ giao diện.
        """
        try:
            # Lấy thông số từ giao diện
            host = self.ui.line_host_server.text()
            port = int(self.ui.line_port_server.text())
            
            # Ghi log thông số server
            self.ui_logger.info(f"Khởi tạo server: Host={host}, Port={port}")
            
            # Khởi tạo server với thông số từ giao diện
            self.tcp_server = Server(
                host=host,
                port=port,
                logger=self.ui_logger,
                log_signals=self.ui_logger_text,
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
            self.ui_logger.info(f"Khởi tạo hệ thống: LogDir={log_dir}, LogSize={log_size}GB, Database={database_path}, AutoStart={auto_start}")
            
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

    def init_all_modules(self):
        """
        Khởi tạo tất cả các module theo thông số từ giao diện.
        """
        # Khởi tạo system
        system_ok = self.init_system()
        if not system_ok:
            self.ui_logger.warning("Không thể khởi tạo hệ thống với thông số từ giao diện, sử dụng thông số mặc định")
        
        # Khởi tạo server
        server_ok = self.init_server()
        if not server_ok:
            self.ui_logger.warning("Không thể khởi tạo server với thông số từ giao diện, sử dụng thông số mặc định")
        
        # Khởi tạo lighting
        lighting_ok = self.init_lighting()
        if not lighting_ok:
            self.ui_logger.warning("Không thể khởi tạo lighting với thông số từ giao diện, sử dụng thông số mặc định")
        
        # Khởi tạo camera
        camera_ok = self.init_camera()
        if not camera_ok:
            self.ui_logger.warning("Không thể khởi tạo camera với thông số từ giao diện, sử dụng thông số mặc định")
        
        return system_ok and server_ok and lighting_ok and camera_ok

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
        """
        Xử lý sự kiện khi nhấn nút Start.
        Khởi động luồng auto.
        """
        try:
            self.ui_logger.info("Bắt đầu khởi động hệ thống Auto")
            
            # Khởi tạo lại các module nếu cần
            init_ok = self.init_all_modules()
            
            if init_ok:
                # Cập nhật UI
                self.ui.btn_start.setEnabled(False)
                self.ui.btn_stop.setEnabled(True)
                
                # Khởi tạo và bắt đầu luồng auto
                self.auto_thread = AutoThread(self)
                self.auto_thread.start()
                
                # Đặt trạng thái trigger auto
                self.b_trigger_auto = True
                self.b_stop_auto = False
                
                self.ui_logger.info("Hệ thống Auto đã khởi động thành công")
            else:
                self.ui_logger.error("Không thể khởi động hệ thống Auto với thông số hiện tại")
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi động hệ thống Auto: {str(e)}")

    def on_click_stop(self):
        """
        Xử lý sự kiện khi nhấn nút Stop.
        Dừng luồng auto.
        """
        try:
            self.ui_logger.info("Đang dừng hệ thống Auto")
            
            # Đặt trạng thái dừng
            self.b_stop_auto = True
            self.b_trigger_auto = False
            
            # Cập nhật UI
            self.ui.btn_start.setEnabled(True)
            self.ui.btn_stop.setEnabled(False)
            
            self.ui_logger.info("Hệ thống Auto đã dừng thành công")
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi dừng hệ thống Auto: {str(e)}")

    def on_click_start_teaching(self):
        """
        Xử lý sự kiện khi nhấn nút Start Teaching.
        Khởi động luồng teaching.
        """
        try:
            self.ui_logger.info("Bắt đầu khởi động hệ thống Teaching")
            
            # Cập nhật UI
            self.ui.btn_start_teaching.setEnabled(False)
            
            # Khởi tạo và bắt đầu luồng teaching
            self.teaching_thread = TeachingThread(self)
            self.teaching_thread.start()
            
            # Đặt trạng thái trigger teaching
            self.b_trigger_teaching = True
            self.b_stop_teaching = False
            
            self.ui_logger.info("Hệ thống Teaching đã khởi động thành công")
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi khởi động hệ thống Teaching: {str(e)}")

    def on_click_reset(self):
        """
        Xử lý sự kiện khi nhấn nút Reset.
        Dừng tất cả các luồng và thiết lập lại trạng thái.
        """
        try:
            self.ui_logger.info("Đang reset hệ thống")
            
            # Dừng luồng auto
            self.b_stop_auto = True
            self.b_trigger_auto = False
            
            # Dừng luồng teaching
            self.b_stop_teaching = True
            self.b_trigger_teaching = False
            
            # Cập nhật UI
            self.ui.btn_start.setEnabled(True)
            self.ui.btn_stop.setEnabled(False)
            self.ui.btn_start_teaching.setEnabled(True)
            
            # Khôi phục cấu hình mặc định
            self.apply_default_config()
            
            self.ui_logger.info("Hệ thống đã reset thành công")
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi reset hệ thống: {str(e)}")

    def handle_result_auto(self, result):
        """
        Xử lý kết quả từ luồng auto.
        """
        try:
            self.ui_logger.info(f"Nhận kết quả auto: {result.code}, kết quả: {result.result}")
            
            # Cập nhật UI với kết quả
            self.ui.label_result.setText(result.result)
            if result.result == "OK":
                self.ui.label_result.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.ui.label_result.setStyleSheet("color: red; font-weight: bold;")
            
            # Cập nhật thông tin chi tiết
            self.update_stats(result)
            
            # Hiển thị ảnh kết quả
            if result.dst is not None:
                self.canvas_dst.load_pixmap(ndarray2pixmap(result.dst))
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi xử lý kết quả auto: {str(e)}")

    def handle_result_teaching(self, result):
        """
        Xử lý kết quả từ luồng teaching.
        """
        try:
            self.ui_logger.info(f"Nhận kết quả teaching: {result.code}, kết quả: {result.result}")
            
            # Cập nhật UI với kết quả
            # TODO: Thêm xử lý kết quả teaching
            
            # Hiển thị ảnh kết quả
            if result.dst is not None:
                self.canvas_dst.load_pixmap(ndarray2pixmap(result.dst))
            
            # Kích hoạt lại nút start teaching
            self.ui.btn_start_teaching.setEnabled(True)
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi xử lý kết quả teaching: {str(e)}")

    def update_stats(self, result):
        """
        Cập nhật thống kê trong UI.
        """
        try:
            # Đếm số lượng OK/NG
            ok_count = int(self.ui.label_text_ok.text() or "0")
            ng_count = int(self.ui.label_text_ng.text() or "0")
            total_count = int(self.ui.label_text_total.text() or "0")
            
            # Cập nhật theo kết quả
            if result.result == "OK":
                ok_count += 1
            else:
                ng_count += 1
            
            total_count += 1
            rate = (ok_count / total_count) * 100 if total_count > 0 else 0
            
            # Cập nhật UI
            self.ui.label_text_ok.setText(str(ok_count))
            self.ui.label_text_ng.setText(str(ng_count))
            self.ui.label_text_total.setText(str(total_count))
            self.ui.label_text_rate.setText(f"{rate:.2f}%")
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi cập nhật thống kê: {str(e)}")

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
        config["shapes"] = {
            shape.label: shape.cvBox for shape in self.canvas_src.shapes
        }
        
        # Lưu thông tin về các module
        config["modules"] = {}
        
        # Lưu thiết lập liên quan đến camera
        config["modules"]["camera"] = {
            "type": self.ui.combo_type_camera.currentText(),
            "id": self.ui.combo_id_camera.currentText(),
            "feature": self.ui.combo_feature.currentText()
        }
        
        # Lưu thiết lập liên quan đến lighting
        config["modules"]["lighting"] = {
            "controller": self.ui.combo_controller.currentText(),
            "com": self.ui.combo_comport.currentText(),
            "baudrate": self.ui.combo_baudrate.currentText(),
            "delay": self.ui.spin_delay.value(),
            "channels": [
                self.ui.spin_channel_0.value(),
                self.ui.spin_channel_1.value(),
                self.ui.spin_channel_2.value(),
                self.ui.spin_channel_3.value()
            ]
        }
        
        # Lưu thiết lập liên quan đến server
        config["modules"]["server"] = {
            "host": self.ui.line_host_server.text(),
            "port": self.ui.line_port_server.text()
        }
        
        # Lưu thiết lập liên quan đến hệ thống
        config["modules"]["system"] = {
            "log_dir": self.ui.line_log_dir.text(),
            "log_size": self.ui.line_log_size.text(),
            "database_path": self.ui.line_database_path.text(),
            "auto_start": self.ui.check_auto_start.isChecked()
        }
        
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
        
        # Ghi nhật ký cấu hình
        self.ui_logger.debug(
            f"Get config: {json.dumps(config, indent=4, ensure_ascii=False)}"
        )
        
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
            
            # Ghi nhật ký trước khi áp dụng cấu hình
            self.ui_logger.debug(
                f"Setting config: {json.dumps(config, indent=4, ensure_ascii=False)}"
            )
            
            # Áp dụng cấu hình shapes nếu có
            if "shapes" in config:
                # Xóa các hình dạng hiện tại
                self.canvas_src.shapes.clear()
                
                # Thêm shapes mới từ cấu hình
                for label, box in config["shapes"].items():
                    shape = Shape(label=label)
                    shape.cvBox = box
                    self.canvas_src.shapes.append(shape)
                
                # Vẽ lại canvas
                self.canvas_src.repaint()
            
            # Áp dụng cấu hình modules nếu có
            if "modules" in config:
                modules = config["modules"]
                
                # Áp dụng cấu hình camera
                if "camera" in modules:
                    camera_config = modules["camera"]
                    self.add_combox_item(self.ui.combo_type_camera, ["Webcam", "HIK", "SODA"])
                    self.add_combox_item(self.ui.combo_id_camera, ["0", "1", "2"])
                    self.add_combox_item(self.ui.combo_feature, ["RGB", "HSV"])
                    self.set_combobox_text(self.ui.combo_type_camera, camera_config.get("type", "Webcam"))
                    self.set_combobox_text(self.ui.combo_id_camera, camera_config.get("id", ""))
                    self.set_combobox_text(self.ui.combo_feature, camera_config.get("feature", ""))
                
                # Áp dụng cấu hình lighting
                if "lighting" in modules:
                    lighting_config = modules["lighting"]
                    self.add_combox_item(self.ui.combo_controller, ["LCP", "DCP"])
                    self.add_combox_item(self.ui.combo_comport, ["COM9", "COM10"])
                    self.add_combox_item(self.ui.combo_baudrate, ["9600", "19200"])
                    self.set_combobox_text(self.ui.combo_controller, lighting_config.get("controller", "LCP"))
                    self.set_combobox_text(self.ui.combo_comport, lighting_config.get("com", "COM9"))
                    self.set_combobox_text(self.ui.combo_baudrate, lighting_config.get("baudrate", "9600"))
                    
                    # Đặt giá trị cho spinbox
                    self.ui.spin_delay.setValue(lighting_config.get("delay", 200))
                    
                    # Đặt giá trị cho các kênh
                    channels = lighting_config.get("channels", [10, 10, 10, 10])
                    if len(channels) >= 4:
                        self.ui.spin_channel_0.setValue(channels[0])
                        self.ui.spin_channel_1.setValue(channels[1])
                        self.ui.spin_channel_2.setValue(channels[2])
                        self.ui.spin_channel_3.setValue(channels[3])
                
                # Áp dụng cấu hình server
                if "server" in modules:
                    server_config = modules["server"]
                    self.ui.line_host_server.setText(server_config.get("host", "127.0.0.1"))
                    self.ui.line_port_server.setText(str(server_config.get("port", 8080)))
                
                # Áp dụng cấu hình system
                if "system" in modules:
                    system_config = modules["system"]
                    self.ui.line_log_dir.setText(system_config.get("log_dir", "logs"))
                    self.ui.line_log_size.setText(str(system_config.get("log_size", 10)))
                    self.ui.line_database_path.setText(system_config.get("database_path", "database.db"))
                    self.ui.check_auto_start.setChecked(system_config.get("auto_start", False))
            
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
        
        # Đồng bộ với combo_model chính
        index = self.ui.combo_model.findText(model_name)
        if index >= 0:
            self.ui.combo_model.setCurrentIndex(index)
        
        # Tải model
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
                model_name = self.ui.combo_model.currentText()
            
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
            
            # Cập nhật combobox hiện tại nếu cần
            if model_name != self.ui.combo_model.currentText():
                index = self.ui.combo_model.findText(model_name)
                if index >= 0:
                    self.ui.combo_model.setCurrentIndex(index)
            
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
            index = self.ui.combo_model.findText(model_name)
            if index >= 0:
                self.ui.combo_model.setCurrentIndex(index)
                
            index = self.ui.combo_model_setting.findText(model_name)
            if index >= 0:
                self.ui.combo_model_setting.setCurrentIndex(index)
            
            # Tải model mới (không cần gọi lại vì đã thiết lập currentIndex sẽ trigger on_change_model)
            self.ui_logger.info(f"Đã thêm và tải model mới: {model_name}")
            return True
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi thêm model mới: {str(e)}")
            return False
        
    def on_click_delete(self):
        self.delete_model()

    def delete_model(self, model_name=None):
        """
        Xóa một model.
        Nếu xóa model hiện tại, sẽ tải model khác hoặc áp dụng cấu hình mặc định.
        
        Args:
            model_name (str, optional): Tên của model cần xóa.
                Nếu None, sẽ xóa model hiện tại được chọn trong combobox.
        
        Returns:
            bool: True nếu xóa thành công, False nếu thất bại.
        """
        try:
            # Nếu không có tên model, lấy từ combobox
            if model_name is None:
                model_name = self.ui.combo_model.currentText()
            
            # Hiển thị hộp thoại xác nhận
            from PyQt5.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, 
                "Xác nhận xóa", 
                f"Bạn có chắc chắn muốn xóa model {model_name}?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.No:
                self.ui_logger.info("Đã hủy xóa model")
                return False
            
            # Kiểm tra đường dẫn model
            model_path = os.path.join("models", model_name)
            if not os.path.exists(model_path):
                self.ui_logger.error(f"Không tìm thấy model: {model_path}")
                return False
            
            # Kiểm tra xem đây có phải là model hiện tại không
            is_current_model = (model_name == self.ui.combo_model.currentText())
            
            # Xóa thư mục model và tất cả nội dung
            import shutil
            shutil.rmtree(model_path)
            
            # Xóa model khỏi combobox
            index = self.ui.combo_model.findText(model_name)
            if index >= 0:
                self.ui.combo_model.removeItem(index)
                
            index = self.ui.combo_model_setting.findText(model_name)
            if index >= 0:
                self.ui.combo_model_setting.removeItem(index)
            
            # Nếu xóa model hiện tại, cần tải model khác hoặc áp dụng cấu hình mặc định
            if is_current_model:
                if self.ui.combo_model.count() > 0:
                    # Tải model đầu tiên nếu có
                    self.load_model(self.ui.combo_model.itemText(0))
                else:
                    # Áp dụng cấu hình mặc định nếu không còn model nào
                    self.apply_default_config()
            
            self.ui_logger.info(f"Đã xóa model: {model_name}")
            return True
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi xóa model {model_name}: {str(e)}")
            return False
    
    def on_click_save(self):
        self.save_model()

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
                model_name = self.ui.combo_model.currentText()
            
            self.ui_logger.info(f"Đang lưu model: {model_name}")
            
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
            return True
            
        except Exception as e:
            self.ui_logger.error(f"Lỗi khi lưu model {model_name}: {str(e)}")
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
            self.init_camera()
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
            self.init_lighting()
        
            # Mở kết nối với bộ điều khiển
            status = self.light_controller.open()
            if status:
                self.ui_logger.info("Lighting controller connected successfully")
            else:
                self.ui_logger.warning("Failed to connect to lighting controller")
                
            # Bật các kênh đèn theo giá trị từ giao diện
            channels = [
                self.ui.spin_channel_0.value(),
                self.ui.spin_channel_1.value(),
                self.ui.spin_channel_2.value(),
                self.ui.spin_channel_3.value()
            ]
            
            for i, value in enumerate(channels):
                if value > 0:
                    self.light_controller.on_channel(i, value)
                    self.ui_logger.info(f"Turned on channel {i} with intensity {value}")

            self.ui.btn_open_light.setText("Close")
            self.ui.btn_open_light.setProperty("class", "danger")
            update_style(self.ui.btn_open_light)
        except Exception as e:
            self.ui_logger.error(f"Error Open Light: {e}")

    def close_light(self):
        try:
             # Tắt tất cả các kênh đèn
            channels = [
                self.ui.spin_channel_0.value(),
                self.ui.spin_channel_1.value(),
                self.ui.spin_channel_2.value(),
                self.ui.spin_channel_3.value()
            ]
            
            for i, value in enumerate(channels):
                if value > 0:
                    self.light_controller.off_channel(i)
                    self.ui_logger.info(f"Turned off channel {i}")
            
            # Đóng kết nối với bộ điều khiển
            status = self.light_controller.close()
            if status:
                self.ui_logger.info("Lighting controller disconnected successfully")
            else:
                self.ui_logger.warning("Failed to disconnect from lighting controller")

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

            self.init_server()
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
