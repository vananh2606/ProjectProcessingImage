import socket
import threading
import json
import time
from PyQt5.QtCore import QObject, pyqtSignal


class Server(QObject):
    """
    Class quản lý TCP server.
    """

    # Định nghĩa signals
    clientConnected = pyqtSignal(str, str)  # (host, address)
    clientDisconnected = pyqtSignal(str, str)  # (host, address)
    dataReceived = pyqtSignal(str, str, str)  # (host, address, data)
    serverStarted = pyqtSignal(str, int)  # (host, port)
    serverStopped = pyqtSignal()

    def __init__(self, host="127.0.0.1", port=8080, logger=None, log_signals=None):
        """
        Khởi tạo TCP Server.

        Args:
            host (str): Địa chỉ IP lắng nghe
            port (int): Cổng lắng nghe
            logger: Logger instance từ log_model
            log_signals: Signal instance từ log_model
        """
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = {}  # Lưu trữ các client kết nối {(address, port): socket}
        self.threads = []
        self.logger = logger
        self.log_signals = log_signals

    def start(self):
        """
        Khởi động TCP server.
        """
        if self.running:
            self._log("Server đã chạy", "WARNING")
            return False

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True

            self._log(
                f"Server khởi động tại HOST: {self.host}, PORT: {self.port}", "INFO"
            )
            self.serverStarted.emit(self.host, self.port)

            # Bắt đầu luồng lắng nghe kết nối
            self.accept_thread = threading.Thread(target=self._accept_connections)
            self.accept_thread.daemon = True
            self.accept_thread.start()
            return True
        except Exception as e:
            self._log(f"Không thể khởi động server: {str(e)}", "ERROR")
            return False

    def stop(self):
        """
        Dừng TCP server.
        """
        if not self.running:
            self._log("Server không chạy", "WARNING")
            return

        self.running = False

        # Đóng tất cả các kết nối client
        for client_info, client_socket in list(self.clients.items()):
            try:
                client_socket.close()
                self._log(
                    f"Đóng kết nối từ HOST: {client_info[0]} - ADDRESS: {client_info[1]}",
                    "INFO",
                )
            except:
                pass

        self.clients.clear()

        # Đóng server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        self._log("Server đã dừng.", "INFO")
        self.serverStopped.emit()

    def send_to_all(self, data):
        """
        Gửi dữ liệu tới tất cả các client.

        Args:
            data (str): Dữ liệu cần gửi
        """
        if not self.running:
            self._log("Server không chạy", "WARNING")
            return

        disconnected = []
        data_bytes = data.encode("utf-8")

        for client_info, client_socket in self.clients.items():
            try:
                self._send_data(client_socket, data_bytes)
                self._log(
                    f"Đã gửi tới {client_info[0]}:{client_info[1]}: {data}", "DEBUG"
                )
            except Exception as e:
                self._log(
                    f"Lỗi gửi tới {client_info[0]}:{client_info[1]}: {str(e)}", "ERROR"
                )
                disconnected.append(client_info)

        # Xóa các client đã ngắt kết nối
        for client_info in disconnected:
            self._handle_disconnect(client_info)

    def send_to_client(self, client_info, data):
        """
        Gửi dữ liệu tới một client cụ thể.

        Args:
            client_info (tuple): (host, address) của client
            data (str): Dữ liệu cần gửi
        """
        if not self.running:
            self._log("Server không chạy", "WARNING")
            return False

        if client_info not in self.clients:
            self._log(
                f"Client HOST:{client_info[0]} - ADDRESS: {client_info[1]} không tồn tại",
                "WARNING",
            )
            return False

        try:
            data_bytes = data.encode("utf-8")
            self._send_data(self.clients[client_info], data_bytes)
            self._log(
                f"Đã gửi tới HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {data}",
                "DEBUG",
            )
            return True
        except Exception as e:
            self._log(
                f"Lỗi gửi tới HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {str(e)}",
                "ERROR",
            )
            self._handle_disconnect(client_info)
            return False

    def _accept_connections(self):
        """
        Xử lý chấp nhận kết nối đến.
        """
        self.server_socket.settimeout(1)  # Timeout để kiểm tra trạng thái running

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_info = (addr[0], addr[1])

                # Thêm client vào danh sách
                self.clients[client_info] = client_socket

                # Bắt đầu thread xử lý nhận dữ liệu
                client_thread = threading.Thread(
                    target=self._handle_client, args=(client_socket, client_info)
                )
                client_thread.daemon = True
                client_thread.start()
                self.threads.append(client_thread)

                self._log(
                    f"Client kết nối HOST: {client_info[0]} - ADDRESS: {client_info[1]}",
                    "INFO",
                )
                self.clientConnected.emit(client_info[0], str(client_info[1]))

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self._log(f"Lỗi chấp nhận kết nối: {str(e)}", "ERROR")
                    time.sleep(1)

    def _handle_client(self, client_socket, client_info):
        """
        Xử lý nhận dữ liệu từ một client.

        Args:
            client_socket (socket): Socket của client
            client_info (tuple): (host, address) của client
        """
        client_socket.settimeout(1)  # Timeout để kiểm tra trạng thái running

        while self.running:
            try:
                # Nhận dữ liệu
                data = self._receive_data(client_socket)

                if not data:  # Client đã ngắt kết nối
                    break

                self._log(
                    f"Nhận từ HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {data}",
                    "DEBUG",
                )
                self.dataReceived.emit(client_info[0], str(client_info[1]), data)

            except socket.timeout:
                continue
            except Exception as e:
                self._log(
                    f"Lỗi nhận dữ liệu từ HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {str(e)}",
                    "ERROR",
                )
                break

        self._handle_disconnect(client_info)

    def _handle_disconnect(self, client_info):
        """
        Xử lý ngắt kết nối client.

        Args:
            client_info (tuple): (address, port) của client
        """
        if client_info in self.clients:
            try:
                self.clients[client_info].close()
            except:
                pass

            del self.clients[client_info]
            self._log(
                f"Client ngắt kết nối HOST: {client_info[0]} - ADDRESS: {client_info[1]}",
                "INFO",
            )
            self.clientDisconnected.emit(client_info[0], str(client_info[1]))

    # Phương thức gửi dữ liệu (sửa đổi) - tương thích với Hercules
    def _send_data(self, sock, data_bytes):
        """
        Gửi dữ liệu qua socket không dùng header length.

        Args:
            sock (socket): Socket cần gửi
            data_bytes (bytes): Dữ liệu dạng bytes cần gửi
        """
        # Gửi dữ liệu trực tiếp không thêm header length (phương thức Hercules)
        sock.sendall(data_bytes)

    # Phương thức nhận dữ liệu (sửa đổi) - tương thích với Hercules
    def _receive_data(self, sock):
        """
        Nhận dữ liệu từ socket không dùng header length.

        Args:
            sock (socket): Socket cần nhận

        Returns:
            str: Dữ liệu nhận được
        """
        # Nhận dữ liệu trực tiếp (phương thức Hercules)
        data_bytes = sock.recv(4096)

        if not data_bytes:
            return None

        # Giải mã và trả về dữ liệu dạng chuỗi
        try:
            return data_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Nếu không thể decode, trả về một chuỗi đại diện cho dữ liệu hex
            return "HEX:" + " ".join(f"{b:02X}" for b in data_bytes)

    def _log(self, message, level="INFO"):
        """
        Ghi log sử dụng log_model.

        Args:
            message (str): Thông báo cần ghi
            level (str): Mức độ log
        """
        if self.logger:
            if level == "DEBUG":
                self.logger.debug(message)
            elif level == "INFO":
                self.logger.info(message)
            elif level == "WARNING":
                self.logger.warning(message)
            elif level == "ERROR":
                self.logger.error(message)
            elif level == "CRITICAL":
                self.logger.critical(message)

        # Nếu không có logger nhưng có log_signals, sử dụng signal
        elif self.log_signals:
            self.log_signals.textSignal.emit(message, level)
