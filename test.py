import socket

HOST = "127.0.0.1"  # Lắng nghe trên localhost
PORT = 12345  # Cổng kết nối

# Tạo socket TCP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)

print(f"Server đang lắng nghe trên {HOST}:{PORT}...")

while True:
    client_socket, client_addr = server_socket.accept()
    print(f"Kết nối từ {client_addr}")

    client_socket.settimeout(5)

    try:
        data = client_socket.recv(1024).decode()
        print(f"Nhận từ client: {data}")
        response = f"Server nhận: {data}"
        client_socket.send(response.encode())

        client_socket.close()
    except socket.timeout:
        print("Timeout! Không nhận được dữ liệu từ client.")
