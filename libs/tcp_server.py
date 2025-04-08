import socket
import threading
import logging
import time
from PyQt5.QtCore import QObject, pyqtSignal


class Server(QObject):
    """
    Class for managing a TCP server.
    """

    # Define signals
    serverStarted = pyqtSignal(str, int)  # (host, port)
    serverStopped = pyqtSignal()
    clientConnected = pyqtSignal(str, str)  # (host, address)
    clientDisconnected = pyqtSignal(str, str)  # (host, address)
    dataReceived = pyqtSignal(str, str, str)  # (host, address, data)
    clientLocked = pyqtSignal(str, str)  # (host, address)
    clientUnlocked = pyqtSignal()

    def __init__(self, host="127.0.0.1", port=8080, logger=None):
        """
        Initialize TCP Server.
        

        Args:
            host (str): IP address to listen on
            port (int): Port to listen on
            logger: Logger instance (can be None)
            log_signals: Signal instance (can be None for backward compatibility)
        """
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = {}  # Store connected clients {(host, address): socket}
        self.threads = []
        self.logger = logger if logger else self._setup_default_logger()
        self.locked_client = None  # Client locked for exclusive communication
        self.is_locked = False  # Server lock status

    def _setup_default_logger(self):
        """
        Set up a default logger if none is provided.
        
        Returns:
            logging.Logger: Configured logger instance
        """
        logger = logging.getLogger('TCP_Server')
        logger.setLevel(logging.DEBUG)
        
        # Check if logger already has handlers to avoid duplicates
        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - [%(name)s] - [%(levelname)s] : %(message)s')
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
        
        return logger

    def start(self):
        """
        Start TCP server.
        
        Returns:
            bool: True if started successfully, False otherwise
        """
        if self.running:
            self.logger.warning("Server is already running")
            return False

        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True

            self.logger.info(f"Server started at HOST: {self.host}, PORT: {self.port}")
            self.serverStarted.emit(self.host, self.port)

            # Start the connection listening thread
            self.accept_thread = threading.Thread(target=self._accept_connections)
            self.accept_thread.daemon = True
            self.accept_thread.start()
            return True
        except Exception as e:
            self.logger.error(f"Cannot start server: {str(e)}")
            return False

    def stop(self):
        """
        Stop the TCP server.
        """
        if not self.running:
            self.logger.warning("Server is not running")
            return

        self.running = False
        self.is_locked = False
        self.locked_client = None

        # Close all client connections
        for client_info, client_socket in list(self.clients.items()):
            try:
                client_socket.close()
                self.logger.info(
                    f"Closed connection from HOST: {client_info[0]} - ADDRESS: {client_info[1]}"
                )
            except:
                pass

        self.clients.clear()

        # Close server socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass

        self.logger.info("Server stopped.")
        self.serverStopped.emit()

    def lock_to_client(self, client_info):
        """
        Lock server to communicate only with a selected client.

        Args:
            client_info (tuple): (host, address) of client to lock

        Returns:
            bool: True if locked successfully, False otherwise
        """
        if not self.running:
            self.logger.warning("Server is not running")
            return False

        if client_info not in self.clients:
            self.logger.warning(
                f"Client HOST:{client_info[0]} - ADDRESS: {client_info[1]} does not exist"
            )
            return False

        # Disconnect all other clients
        for other_client in list(self.clients.keys()):
            if other_client != client_info:
                try:
                    self.clients[other_client].close()
                    self.logger.info(
                        f"Disconnected HOST: {other_client[0]} - ADDRESS: {other_client[1]} due to server lock"
                    )
                    del self.clients[other_client]
                    self.clientDisconnected.emit(other_client[0], str(other_client[1]))
                except Exception as e:
                    self.logger.error(
                        f"Error disconnecting HOST: {other_client[0]} - ADDRESS: {other_client[1]}: {str(e)}"
                    )

        self.locked_client = client_info
        self.is_locked = True
        self.logger.info(
            f"Server locked to connection with HOST: {client_info[0]} - ADDRESS: {client_info[1]}"
        )
        self.clientLocked.emit(client_info[0], str(client_info[1]))
        return True

    def unlock_client(self):
        """
        Unlock server to allow connections from multiple clients.

        Returns:
            bool: True if unlocked successfully, False otherwise
        """
        if not self.running:
            self.logger.warning("Server is not running")
            return False

        if not self.is_locked:
            self.logger.warning("Server is not locked")
            return False

        self.locked_client = None
        self.is_locked = False
        self.logger.info("Server unlocked, allowing multiple connections")
        self.clientUnlocked.emit()
        return True

    def send_to_all(self, data):
        """
        Send data to all clients.

        Args:
            data (str): Data to send
        """
        if not self.running:
            self.logger.warning("Server is not running")
            return

        # If server is locked, only send to locked client
        if self.is_locked and self.locked_client:
            return self.send_to_client(self.locked_client, data)

        disconnected = []
        data_bytes = data.encode("utf-8")

        for client_info, client_socket in self.clients.items():
            try:
                self._send_data(client_socket, data_bytes)
                self.logger.debug(
                    f"Sent to {client_info[0]}:{client_info[1]}: {data}"
                )
            except Exception as e:
                self.logger.error(
                    f"Error sending to {client_info[0]}:{client_info[1]}: {str(e)}"
                )
                disconnected.append(client_info)

        # Remove disconnected clients
        for client_info in disconnected:
            self._handle_disconnect(client_info)

    def send_to_client(self, client_info, data):
        """
        Send data to a specific client.

        Args:
            client_info (tuple): (host, address) of client
            data (str): Data to send
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.running:
            self.logger.warning("Server is not running")
            return False

        # If server is locked and client is not the locked client
        if self.is_locked and client_info != self.locked_client:
            self.logger.warning(
                f"Server is locked to another client, cannot send to HOST: {client_info[0]} - ADDRESS: {client_info[1]}"
            )
            return False

        if client_info not in self.clients:
            self.logger.warning(
                f"Client HOST:{client_info[0]} - ADDRESS: {client_info[1]} does not exist"
            )
            return False

        try:
            data_bytes = data.encode("utf-8")
            self._send_data(self.clients[client_info], data_bytes)
            self.logger.debug(
                f"Sent to HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {data}"
            )
            return True
        except Exception as e:
            self.logger.error(
                f"Error sending to HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {str(e)}"
            )
            self._handle_disconnect(client_info)
            return False

    def _accept_connections(self):
        """
        Handle accepting incoming connections.
        """
        self.server_socket.settimeout(1)  # Timeout to check running status

        while self.running:
            try:
                client_socket, addr = self.server_socket.accept()
                client_info = (addr[0], addr[1])

                # If server is locked, reject new connections
                if self.is_locked:
                    self.logger.info(
                        f"Rejected connection from HOST: {client_info[0]} - ADDRESS: {client_info[1]} because server is locked"
                    )
                    client_socket.close()
                    continue

                # Add client to list
                self.clients[client_info] = client_socket

                # Start thread for handling data reception
                client_thread = threading.Thread(
                    target=self._handle_client, args=(client_socket, client_info)
                )
                client_thread.daemon = True
                client_thread.start()
                self.threads.append(client_thread)

                self.logger.info(
                    f"Client connected HOST: {client_info[0]} - ADDRESS: {client_info[1]}"
                )
                self.clientConnected.emit(client_info[0], str(client_info[1]))

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error accepting connection: {str(e)}")
                    time.sleep(1)

    def _handle_client(self, client_socket, client_info):
        """
        Handle receiving data from a client.

        Args:
            client_socket (socket): Client socket
            client_info (tuple): (host, address) of client
        """
        client_socket.settimeout(1)  # Timeout to check running status

        while self.running:
            try:
                # If server is locked and client is not the locked client
                if self.is_locked and client_info != self.locked_client:
                    self.logger.info(
                        f"Disconnecting HOST: {client_info[0]} - ADDRESS: {client_info[1]} because server is locked to another client"
                    )
                    break

                # Receive data
                data = self._receive_data(client_socket)

                if not data:  # Client has disconnected
                    break

                self.logger.debug(
                    f"Received from HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {data}"
                )
                self.dataReceived.emit(client_info[0], str(client_info[1]), data)

            except socket.timeout:
                continue
            except Exception as e:
                self.logger.error(
                    f"Error receiving data from HOST: {client_info[0]} - ADDRESS: {client_info[1]}: {str(e)}"
                )
                break

        self._handle_disconnect(client_info)

    def _handle_disconnect(self, client_info):
        """
        Handle client disconnection.

        Args:
            client_info (tuple): (address, port) of client
        """
        if client_info in self.clients:
            try:
                self.clients[client_info].close()
            except:
                pass

            del self.clients[client_info]
            self.logger.info(
                f"Client disconnected HOST: {client_info[0]} - ADDRESS: {client_info[1]}"
            )
            self.clientDisconnected.emit(client_info[0], str(client_info[1]))

            # If disconnected client is the locked client, unlock server
            if self.is_locked and client_info == self.locked_client:
                self.is_locked = False
                self.locked_client = None
                self.logger.info(f"Unlocking server because locked client disconnected")
                self.clientUnlocked.emit()

    # Method to send data (modified) - compatible with Hercules
    def _send_data(self, sock, data_bytes):
        """
        Send data through socket without length header.

        Args:
            sock (socket): Socket to send to
            data_bytes (bytes): Data in bytes format to send
        """
        # Send data directly without adding length header (Hercules method)
        sock.sendall(data_bytes)

    # Method to receive data (modified) - compatible with Hercules
    def _receive_data(self, sock):
        """
        Receive data from socket without length header.

        Args:
            sock (socket): Socket to receive from

        Returns:
            str: Received data
        """
        # Receive data directly (Hercules method)
        data_bytes = sock.recv(4096)

        if not data_bytes:
            return None

        # Decode and return data as string
        try:
            return data_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # If cannot decode, return a string representation of hex data
            return "HEX:" + " ".join(f"{b:02X}" for b in data_bytes)

    def get_locked_client(self):
        """
        Get information about the currently locked client.

        Returns:
            tuple: (host, address) of locked client or None if no locked client
        """
        return self.locked_client

    def is_server_locked(self):
        """
        Check if server is locked.

        Returns:
            bool: True if server is locked, False otherwise
        """
        return self.is_locked