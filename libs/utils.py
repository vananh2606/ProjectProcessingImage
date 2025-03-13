import threading
import os
import time
import json
import math
import cv2
import psutil
import GPUtil
import hashlib
import yaml
from functools import wraps

# ==========================================
# FILE I/O OPERATIONS
# ==========================================


def load_label(path):
    """Tải danh sách nhãn từ file văn bản."""
    lines = []
    try:
        with open(path, "r") as ff:
            lines = ff.readlines()
        return [l.strip().strip("\n") for l in lines]
    except Exception:
        return lines


def save_json(filename, data):
    """Lưu dữ liệu dưới dạng JSON."""
    with open(filename, "w") as ff:
        data_store = json.dumps(data, sort_keys=True, indent=4)
        ff.write(data_store)


def load_json(filename):
    """Tải dữ liệu từ file JSON."""
    with open(filename) as ff:
        data = json.load(ff)
    return data


def load_yaml(path="cameras.yaml"):
    """Tải dữ liệu từ file YAML."""
    with open(path, "r") as file:
        config = yaml.safe_load(file)
    return config


def save_yaml(path, data):
    """Lưu dữ liệu dưới dạng YAML."""
    with open(path, "w") as file:
        yaml.safe_dump(data, file)


def mkdir(folder):
    """Tạo thư mục nếu chưa tồn tại."""
    os.makedirs(folder, exist_ok=True)
    return folder


def scan_dir(folder):
    """Quét thư mục và trả về kích thước (MB)."""
    size = 0
    n = 0
    n_dir = 0
    for path, dirs, files in os.walk(folder):
        n_dir += len(dirs)
        for f in files:
            fp = os.path.join(path, f)
            n += 1
            try:
                size += os.path.getsize(fp)
            except Exception:
                pass

    return size / (1024**2)  # Chuyển đổi sang MB


# ==========================================
# DATA TYPE CONVERSIONS
# ==========================================


def str2int(s, default=0):
    """Chuyển đổi chuỗi thành số nguyên."""
    try:
        return int(s)
    except Exception:
        return default


def str2float(s, default=0.0):
    """Chuyển đổi chuỗi thành số thực."""
    try:
        return float(s)
    except Exception:
        return default


def str2ListInt(string, sep=","):
    """Chuyển đổi chuỗi thành danh sách số nguyên."""
    lst = string.split(sep)
    return [int(l) for l in lst]


def str2ListFloat(string, sep=","):
    """Chuyển đổi chuỗi thành danh sách số thực."""
    lst = string.split(sep)
    return [float(l) for l in lst]


def bin2dec(b):
    """Chuyển đổi số nhị phân sang thập phân."""
    p = 0
    dec = 0
    r = 0
    n = -1
    while b >= 2:
        r = b % 10
        b = (b - r) // 10
        n += 1
        dec += math.pow(2, n) * r
    dec += math.pow(2, n + 1) * b
    return int(dec)


def rgb_to_hex(rgb):
    """Chuyển đổi RGB thành mã màu hex."""
    return "#%02x%02x%02x" % rgb


# ==========================================
# IMAGE PROCESSING
# ==========================================


def t_img(mat):
    """Chuyển vị ma trận ảnh."""
    if len(mat.shape) == 2:
        return mat.T
    else:
        b, g, r = cv2.split(mat)
        bT = b.T
        gT = g.T
        rT = r.T
        return cv2.merge((bT, gT, rT))


def cv_rotated(mat, deg):
    """Xoay ảnh theo góc (90, 180, 270 độ)."""
    if deg == 90:
        return cv2.flip(t_img(mat), 1)
    elif deg == 180:
        return cv2.flip(mat, -1)
    elif deg == 270:
        return cv2.flip(t_img(mat), 0)
    return mat  # Trả về ảnh gốc nếu góc không hợp lệ


# ==========================================
# SYSTEM RESOURCES
# ==========================================


def get_cpu_ram_usage():
    """Lấy thông tin sử dụng CPU và RAM."""
    d = dict(psutil.virtual_memory()._asdict())
    cpu = psutil.cpu_percent()
    physical_memory = d["used"] / d["total"] * 100
    return (cpu, physical_memory)


def get_list_gpus():
    """Lấy danh sách GPU trong hệ thống."""
    try:
        return GPUtil.getGPUs()
    except Exception:
        return []


def get_hardware_resoures():
    """Lấy thông tin tài nguyên phần cứng."""
    resources = {"cpu": {}, "gpu": {}, "ram": {}}

    resources["cpu"]["percent"] = psutil.cpu_percent(interval=1)
    resources["ram"]["percent"] = psutil.virtual_memory().percent

    gpus = get_list_gpus()
    resources["gpus"] = {}
    for i, gpu in enumerate(gpus):
        resources["gpus"][i] = {
            "name": gpu.name,
            "percent": gpu.load,
            "temperature": gpu.temperature,
        }

    return resources


# ==========================================
# UTILITY FUNCTIONS
# ==========================================


def format_ex(ex):
    """Format exception thành chuỗi."""
    return f"{type(ex)}: {ex}"


def generateColorByText(text):
    """Tạo màu dựa trên văn bản."""
    s = text
    hashCode = int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)
    r = int((hashCode / 255) % 255)
    g = int((hashCode / 65025) % 255)
    b = int((hashCode / 16581375) % 255)
    return (r, g, b)


def sorting_pair(l1, l2, key, reverse=False):
    """Sắp xếp hai danh sách song song theo khóa."""
    a = list(zip(*sorted(zip(l1, l2), key=key, reverse=reverse)))
    if len(a):
        return list(a[0]), list(a[1])
    else:
        return l1, l2


def runThread(target, args=(), daemon=False):
    """Chạy một hàm trong thread riêng biệt."""
    thread = threading.Thread(target=target, args=args, daemon=daemon)
    thread.start()
    return thread


def decorator_dt(f):
    """Decorator để đo thời gian thực thi của hàm."""
    t0 = time.time()

    @wraps(f)
    def wrapper(*args, **kwds):
        try:
            return f(*args, **kwds)
        finally:
            print(f"Thời gian thực thi {f.__name__}: {time.time() - t0:.6f}s")

    return wrapper


if __name__ == "__main__":
    pass
