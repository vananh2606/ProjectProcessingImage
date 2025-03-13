from PyQt5.QtGui import *
from PyQt5.QtCore import *

import numpy as np

# ==========================================
# DEFAULT COLOR SETTINGS
# ==========================================

# Color settings for shapes
DEFAULT_FILL_COLOR = QColor(128, 128, 255, 100)
DEFAULT_SELECT_FILL_COLOR = QColor(255, 100, 100, 50)
DEFAULT_VISIBLE_FILL_COLOR = QColor(128, 128, 0, 0)
DEFAULT_VERTEX_FILL_COLOR = QColor(255, 255, 255, 0)
DEFAULT_VERTEX_SELECT_FILL_COLOR = QColor(255, 255, 0, 255)
DEFAULT_SELECT_COLOR = QColor(255, 0, 0, 255)


class Shape(object):
    """
    Lớp Shape đại diện cho một hình chữ nhật được xác định bởi 4 điểm góc.
    Hỗ trợ các thao tác vẽ, di chuyển, thay đổi kích thước và quản lý trạng thái.
    """

    # Các thông số cơ bản của Shape
    RADIUS = 20  # Bán kính của điểm góc khi hiển thị
    THICKNESS = 3  # Độ dày của đường viền
    FONT_SIZE = 25  # Kích thước font chữ cho nhãn
    MIN_WIDTH = 10  # Kích thước tối thiểu của shape

    def __init__(self, label=None):
        """
        Khởi tạo một shape mới với nhãn tùy chọn.

        Args:
            label (str, optional): Nhãn của shape. Defaults to None.
        """
        super(Shape, self).__init__()

        # Thuộc tính cơ bản
        self.points = []  # Danh sách các điểm góc
        self.label = label  # Nhãn của shape

        # Trạng thái của shape
        self.selected = False  # Shape có được chọn hay không
        self.visible = False  # Shape có đang được xem xét hay không
        self.corner = None  # Chỉ số của góc được chọn
        self._b_lock = False  # Shape có bị khóa không
        self._b_hide = False  # Shape có bị ẩn không

        # Các thuộc tính phụ
        self.image_debug = None  # Hình ảnh debug
        self.config = None  # Cấu hình bổ sung
        self.scale = 1.0  # Tỉ lệ hiển thị

        # Thuộc tính màu sắc
        self.vertex_fill_color = DEFAULT_VERTEX_FILL_COLOR
        self.vertex_select_fill_color = DEFAULT_VERTEX_SELECT_FILL_COLOR
        self.fill_color = DEFAULT_FILL_COLOR
        self.select_color = DEFAULT_SELECT_COLOR
        self.select_fill_color = DEFAULT_SELECT_FILL_COLOR
        self.visible_fill_color = DEFAULT_VISIBLE_FILL_COLOR

    # ==========================================
    # PROPERTY GETTERS & SETTERS
    # ==========================================

    @property
    def lock(self):
        """Trả về trạng thái khóa của shape."""
        return self._b_lock

    @lock.setter
    def lock(self, val: bool):
        """Đặt trạng thái khóa của shape."""
        self._b_lock = val

    @property
    def hide(self):
        """Trả về trạng thái ẩn của shape."""
        return self._b_hide

    @hide.setter
    def hide(self, val: bool):
        """Đặt trạng thái ẩn của shape."""
        self._b_hide = val

    @property
    def cvBox(self):
        """
        Chuyển đổi shape thành hình chữ nhật OpenCV (x, y, w, h).
        Đảm bảo tọa độ không âm.
        """
        tl = self.points[0]  # Top-left
        br = self.points[2]  # Bottom-right
        x, y = tl.x(), tl.y()
        w, h = br.x() - x, br.y() - y

        x, y, w, h = list(map(int, [x, y, w, h]))
        x = max(x, 0)
        y = max(y, 0)
        return [x, y, w, h]

    # ==========================================
    # DRAWING METHODS
    # ==========================================

    def drawVertex(self, path, i):
        """
        Vẽ điểm góc thứ i của shape vào path.

        Args:
            path (QPainterPath): Đường dẫn để vẽ
            i (int): Chỉ số của điểm góc
        """
        d = max(int(Shape.RADIUS / (self.scale + 1e-5)), 10)
        point = self.points[i]

        # Vẽ hình khác nhau tùy thuộc vào trạng thái của góc
        if self.corner is not None and i == self.corner:
            # Nếu là góc được chọn, vẽ hình vuông
            path.addRect(point.x() - d, point.y() - d, 2 * d, 2 * d)
        elif self.visible:
            # Nếu shape đang được xem xét, vẽ hình tròn nhỏ hơn
            path.addEllipse(point, d / 2, d / 2)
        else:
            # Trường hợp mặc định
            path.addEllipse(point, d / 2.0, d / 2.0)

    def paint(self, painter, s=1):
        """
        Vẽ shape lên painter với tỉ lệ s.

        Args:
            painter (QPainter): Đối tượng để vẽ
            s (float, optional): Tỉ lệ vẽ. Defaults to 1.
        """
        # Nếu shape bị ẩn, không vẽ
        if self.hide:
            return

        self.scale = s

        # Thiết lập bút vẽ
        color = Qt.green
        lw = max(int(Shape.THICKNESS / (self.scale + 1e-5)), 1)
        painter.setPen(QPen(color, lw))

        # Tạo đường dẫn cho đường viền và các điểm góc
        line_path = QPainterPath()
        vertex_path = QPainterPath()

        # Vẽ đường viền
        line_path.moveTo(self.points[0])
        for i, p in enumerate(self.points):
            line_path.lineTo(p)
            self.drawVertex(vertex_path, i)
        line_path.lineTo(self.points[0])  # Đóng đường viền

        # Vẽ đường viền
        painter.drawPath(line_path)

        # Vẽ nhãn
        if self.label is not None:
            fs = max(int(Shape.FONT_SIZE / (self.scale + 1e-5)), 20)
            font = QFont("Arial", fs)
            painter.setFont(font)
            painter.drawText(int(self[0].x()) - 1, int(self[0].y()) - 1, self.label)

        # Tô màu cho các điểm góc
        # Chọn màu dựa trên trạng thái của shape
        color = (
            self.vertex_select_fill_color
            if (self.visible or self.corner is not None)
            else self.vertex_fill_color
        )
        color = self.select_color if self.selected else color
        painter.fillPath(vertex_path, color)

    # ==========================================
    # MANIPULATION METHODS
    # ==========================================

    def translate_(self, v: QPointF):
        """
        Di chuyển shape theo vector v mà không kiểm tra khóa.

        Args:
            v (QPointF): Vector di chuyển
        """
        self.points = [p + v for p in self.points]

    def move(self, v: QPointF):
        """
        Di chuyển shape theo vector v nếu không bị khóa.

        Args:
            v (QPointF): Vector di chuyển
        """
        if not self.lock:
            self.points = [p + v for p in self.points]

    def copy(self):
        """
        Tạo bản sao của shape hiện tại với nhãn mới và vị trí dịch chuyển.

        Returns:
            Shape: Bản sao của shape
        """
        shape = Shape(label=self.label + "_copy")
        shape.points = self.points.copy()
        shape.visible = self.visible
        shape.corner = self.corner
        shape.config = self.config
        shape.translate_(QPointF(50.0, 50.0))  # Dịch chuyển bản sao
        return shape

    def change(self, v):
        """
        Thay đổi kích thước shape bằng cách di chuyển góc được chọn.

        Args:
            v (QPointF): Vector di chuyển
        """
        if self.lock:
            return

        points = self.points
        corner = self.corner
        R = QRectF(self.points[0], self.points[2])
        pos = self.points[corner] + v

        # Thay đổi hình chữ nhật dựa trên góc được chọn
        if corner == 0:
            R.setTopLeft(pos)
        elif corner == 1:
            R.setTopRight(pos)
        elif corner == 2:
            R.setBottomRight(pos)
        elif corner == 3:
            R.setBottomLeft(pos)

        # Cập nhật các điểm nếu hình chữ nhật hợp lệ
        ret, points = self.get_points(R)
        if ret:
            self.points = points

    def get_points(self, r=QRectF()):
        """
        Lấy 4 điểm góc từ hình chữ nhật r và kiểm tra kích thước tối thiểu.

        Args:
            r (QRectF, optional): Hình chữ nhật. Defaults to QRectF().

        Returns:
            tuple: (ret, points) với ret là True nếu hình chữ nhật hợp lệ
        """
        pos1 = r.topLeft()
        pos2 = r.topRight()
        pos3 = r.bottomRight()
        pos4 = r.bottomLeft()

        width = pos3.x() - pos1.x()
        height = pos3.y() - pos1.y()

        # Kiểm tra kích thước tối thiểu
        if width > Shape.MIN_WIDTH and height > Shape.MIN_WIDTH:
            ret = True
        else:
            ret = False
        return ret, [pos1, pos2, pos3, pos4]

    # ==========================================
    # DETECTION AND TESTING METHODS
    # ==========================================

    def contain(self, pos):
        """
        Kiểm tra xem điểm pos có nằm trong shape hay không.

        Args:
            pos (QPointF): Điểm cần kiểm tra

        Returns:
            bool: True nếu pos nằm trong shape
        """
        x, y = pos.x(), pos.y()
        tl = self.points[0]  # Top-left
        br = self.points[2]  # Bottom-right
        x1, y1 = tl.x(), tl.y()
        x2, y2 = br.x(), br.y()
        return x1 < x < x2 and y1 < y < y2

    def get_corner(self, pos, epsilon=10):
        """
        Kiểm tra xem điểm pos có gần với góc nào của shape hay không.

        Args:
            pos (QPointF): Điểm cần kiểm tra
            epsilon (int, optional): Ngưỡng khoảng cách. Defaults to 10.

        Returns:
            bool: True nếu pos gần với một góc
        """
        for i in range(len(self.points)):
            d = self.distance(pos, self.points[i])
            if d < epsilon:
                self.corner = i
                return True
        self.corner = None
        return False

    def distance(self, p1, p2):
        """
        Tính khoảng cách Euclidean giữa hai điểm.

        Args:
            p1, p2 (QPointF): Hai điểm cần tính khoảng cách

        Returns:
            float: Khoảng cách Euclidean
        """
        p = p2 - p1
        return np.sqrt(p.x() ** 2 + p.y() ** 2)

    def dis_to(self, pos):
        """
        Tính khoảng cách từ điểm pos đến shape.
        Trả về khoảng cách dương nếu pos nằm trong shape, âm nếu nằm ngoài.

        Args:
            pos (QPointF): Điểm cần tính khoảng cách

        Returns:
            float: Khoảng cách đến shape
        """
        x, y = pos.x(), pos.y()
        tl = self.points[0]  # Top-left
        br = self.points[2]  # Bottom-right

        # Tính khoảng cách đến cạnh gần nhất
        dx = min([np.abs(x - tl.x()), np.abs(x - br.x())])
        dy = min([np.abs(y - tl.y()), np.abs(y - br.y())])

        # Trả về khoảng cách dương nếu nằm trong, âm nếu nằm ngoài
        if self.contain(pos):
            return min(dx, dy)
        else:
            return -min(dx, dy)

    # ==========================================
    # CONTAINER BEHAVIOR IMPLEMENTATION
    # ==========================================

    def __len__(self):
        """Trả về số lượng điểm của shape."""
        return len(self.points)

    def __getitem__(self, key):
        """Truy cập điểm theo chỉ số."""
        return self.points[key]

    def __setitem__(self, key, value):
        """Thiết lập điểm theo chỉ số."""
        self.points[key] = value


if __name__ == "__main__":
    pass
