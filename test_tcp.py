import socket
import time

HOST = "127.0.0.1"  # Lắng nghe trên localhost
PORT = 8080  # Cổng kết nối

# Tạo socket TCP
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client_socket.connect((HOST, PORT))

time.sleep(1)
print(f"Server đang lắng nghe trên {HOST}:{PORT}...")

    
try:
    while True:
        client_socket.sendall(b"Check")
        # data = client_socket.recv(1024).decode()
        # print(f"Nhận từ client: {data}")
        # response = f"Server nhận: {data}"
        # client_socket.send(response.encode())
        time.sleep(1)

    client_socket.close()
except socket.timeout:
    print("Timeout! Không nhận được dữ liệu từ client.")
