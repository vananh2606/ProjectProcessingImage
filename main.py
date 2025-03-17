import os
import sys
import time
import logging
import cv2 as cv
from PyQt5.QtWidgets import (
    QMainWindow,
    QApplication,
    QWidget,
    QTabWidget,
    QFileDialog,
    QPushButton,
    QScrollArea,
    QListWidgetItem,
)
from PyQt5.QtCore import Qt, QFile, pyqtSignal, QSize
from PyQt5.QtGui import QImage, QPixmap, QIcon
from functools import partial

from ui.MainWindowUI import Ui_MainWindow

sys.path.append("libs")
from libs.canvas import WindowCanvas, Canvas
from libs.ui_utils import load_style_sheet, ndarray2pixmap
from libs.logger import Logger
from libs.log_model import setup_logger
from libs.image_converter import ImageConverter
from libs.tcp_server import Server
from libs.camera_thread import CameraThread


class MainWindow(QMainWindow):
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
        self.log_path = "logs/logfile"
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
        self.ui.btn_refesh.setProperty("class", "default")
        self.ui.btn_start_teaching.setProperty("class", "success")
        self.ui.btn_open_light.setProperty("class", "success")
        self.ui.btn_connect_server.setProperty("class", "success")
        self.ui.btn_send_client.setProperty("class", "primary")

        # Canvas
        self.canvas_src = Canvas()
        self.ui.verticalLayoutImageSRC.addWidget(WindowCanvas(self.canvas_src))
        self.canvas_binary = Canvas()
        self.ui.verticalLayoutImageBinary.addWidget(WindowCanvas(self.canvas_binary))
        self.canvas_dst = Canvas()
        self.ui.verticalLayoutImageDST.addWidget(WindowCanvas(self.canvas_dst))
        self.canvas_auto = Canvas()
        self.ui.verticalLayoutScreensAuto.addWidget(WindowCanvas(self.canvas_auto))

        # # ScrollBar
        # scroll_bar = self.add_scrollable_tab(self.ui.tabWidgetModule) # Tạo scroll trong tabWidget
        # self.ui.verticalLayoutModuleTeaching.addWidget(scroll_bar) # Thêm scroll vào layout

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

    def on_click_start(self):
        pass

    def on_click_stop(self):
        pass

    def on_click_reset(self):
        pass

    def on_click_add(self):
        pass

    def on_click_delete(self):
        pass

    def on_click_save(self):
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
                self.ui_logger.debug(f"Displaying image: {os.path.basename(file_path)}")

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
            self.camera_thread.open_camera()
            self.ui.btn_start_camera.setEnabled(True)
            self.ui.btn_test_camera.setEnabled(True)
            self.ui.btn_open_camera.setText("Close")
            self.ui.btn_open_camera.setProperty("class", "danger")
            self.ui.btn_open_camera.style().polish(self.ui.btn_open_camera)

            self.ui_logger.info("Camera opened successfully")
        except Exception as e:
            self.ui_logger.error(f"Error Opening Camera: {e}")

    def close_camera(self):
        try:
            self.camera_thread.close_camera()
            self.ui.btn_start_camera.setEnabled(False)
            self.ui.btn_test_camera.setEnabled(False)
            self.ui.btn_open_camera.setText("Open")
            self.ui.btn_open_camera.setProperty("class", "success")
            self.ui.btn_open_camera.style().polish(self.ui.btn_open_camera)
            self.camera_thread = None

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
            self.ui.btn_start_camera.style().polish(self.ui.btn_start_camera)
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
            self.ui.btn_start_camera.style().polish(self.ui.btn_start_camera)
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

    def on_click_refesh(self):
        pass

    def on_click_start_teaching(self):
        pass

    def on_click_open_light(self):
        pass

    def on_click_connect_server(self):
        if self.ui.btn_connect_server.text() == "Connect":
            self.connect_server()
        else:
            self.disconnect_server()

    def connect_server(self):
        try:
            self.ui.btn_connect_server.setText("Disconnect")
            self.tcp_server.start()
        except Exception as ex:
            self.ui_logger.error(str(ex))

    def disconnect_server(self):
        try:
            self.tcp_server.stop()
            self.ui.btn_connect_server.setText("Connect")
        except Exception as ex:
            self.ui_logger.error(str(ex))

    def on_click_send_client(self):
        self.tcp_server.send_to_all("Hello")

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
