from shape import *
import resources
from ui_utils import *
from utils import load_label

from functools import partial

# ==========================================
# CURSOR CONSTANTS
# ==========================================
CURSOR_DEFAULT = Qt.ArrowCursor
CURSOR_POINT = Qt.PointingHandCursor
CURSOR_DRAW = Qt.CrossCursor
CURSOR_DRAW_POLYGON = Qt.SizeAllCursor
CURSOR_MOVE = Qt.ClosedHandCursor
CURSOR_GRAB = Qt.OpenHandCursor


class Canvas(QLabel):
    """
    Canvas là thành phần chính để hiển thị và tương tác với hình ảnh.
    Cho phép người dùng xem, vẽ, chỉnh sửa các shape trên hình ảnh.
    """

    # ==========================================
    # SIGNALS
    # ==========================================
    # Định nghĩa các signals để giao tiếp với các thành phần khác
    mouseMoveSignal = pyqtSignal(QPointF)
    newShapeSignal = pyqtSignal(int)
    editShapeSignal = pyqtSignal(str)
    deleteShapeSignal = pyqtSignal(int)
    moveShapeSignal = pyqtSignal(int)
    drawShapeSignal = pyqtSignal(QRectF)
    changeShapeSignal = pyqtSignal(int)
    selectedShapeSignal = pyqtSignal(int)
    zoomSignal = pyqtSignal(float)
    actionSignal = pyqtSignal(str)
    applyConfigSignal = pyqtSignal()

    def __init__(self, parent=None, bcontext_menu=True, benable_drawing=True):
        """
        Khởi tạo Canvas.

        Args:
            parent: Widget cha
            bcontext_menu (bool): Cho phép menu ngữ cảnh
            benable_drawing (bool): Cho phép vẽ
        """
        super().__init__(parent)
        self.setObjectName("Canvas")

        # Thiết lập cơ bản
        self.bcontext_menu = bcontext_menu
        self.benable_drawing = benable_drawing

        # Cài đặt hiển thị
        self.picture = QPixmap(640, 480)
        self.painter = QPainter()
        self.scale = 1
        self.org = QPointF()

        # Trạng thái
        self.moving = False
        self.edit = False
        self.drawing = False
        self.highlight = False
        self.wheel = False

        # Vị trí con trỏ và vẽ
        self.current_pos = QPointF()
        self.current = None
        self.win_start_pos = QPointF()
        self.start_pos = QPointF()
        self.start_pos_moving = QPointF()
        self.line1 = [QPointF(), QPointF()]
        self.line2 = [QPointF(), QPointF()]
        self.text_pixel_color = "BGR:"

        # Quản lý shapes
        self.shapes = []
        self.idVisible = None
        self.idSelected = None
        self.idCorner = None

        # Cấu hình
        self.label_path = "resources/labels/classes.txt"
        self.labels = load_label(self.label_path)
        self.last_label = ""

        # Hộp thoại chỉnh sửa nhãn
        self.boxEditLabel = BoxEditLabel("Enter shape name", self)

        # Khởi tạo menu ngữ cảnh
        self._init_context_menu()

        # Khởi tạo UI
        self._init_ui()

        # Thiết lập trạng thái ban đầu
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.WheelFocus)

        # Biến cho fullscreen
        self._b_full_screen = False
        self._old_parent = None
        self._geometry = None

    def _init_context_menu(self):
        """Khởi tạo menu ngữ cảnh."""
        self.contextMenu = QMenu()
        action = partial(newAction, self)

        # Tạo các actions
        lock = action("Lock", self.change_lock, "", "lock", "Lock/Unlock shape")
        lock_all = action(
            "Lock All", self.change_lock_all, "", "lock", "Lock/Unlock all shapes"
        )
        hide_all = action(
            "Hide All", self.change_hide_all, "", "lock", "Hide/Show all shapes"
        )
        copy = action("Copy", self.copyShape, "", "copy", "copy shape")
        edit = action("Edit", self.editShape, "", "edit", "edit shape")
        delete = action("Delete", self.deleteShape, "", "delete", "delete shape")
        delete_all = action("Delete All", self.delete_all, "", "", "delete shape")

        # Lưu trữ các actions
        self.actions = struct(
            copy=copy,
            edit=edit,
            delete=delete,
            delete_all=delete_all,
            lock=lock,
            lock_all=lock_all,
            hide_all=hide_all,
        )

        # Thêm vào menu
        addActions(self.contextMenu, [lock, lock_all])
        addActions(self.contextMenu, [hide_all])
        self.contextMenu.addSeparator()
        addActions(self.contextMenu, [edit, copy, delete, delete_all])

        # Thiết lập hiển thị menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.popUpMenu)

    def _init_ui(self):
        """Khởi tạo giao diện người dùng."""
        style = "QLabel{background-color:rgba(128, 128, 128, 150); color:white; font:bold 12px}"

        # Tạo widget chứa toolbar
        self.tool_bar = QWidget(self)

        # Hiển thị thông tin
        self.label_pos = newLabel("", style=style)
        self.label_rect = newLabel("", style=style)
        self.label_color = newLabel("", style=style)
        self.label_pos.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # Nút điều khiển zoom
        self.tool_buttons = newDialogButton(
            self.tool_bar,
            ["Draw rectangle", "Zoom in", "Zoom out", "Fit window", "Full screen"],
            [
                self.active_edit,
                lambda: self.zoom_manual(1.2),
                lambda: self.zoom_manual(0.8),
                lambda: self.fit_window(),
                self.on_show_full_screen,
            ],
            icons=["draw", "zoom_in", "zoom_out", "fit_window", "full_screen"],
            # orient=Qt.Vertical,
            orient=Qt.Horizontal,
        ).buttons()

        # Thiết lập style cho buttons
        for button in self.tool_buttons:
            button.setIconSize(QSize(15, 15))
            button.setProperty("class", "icon")

    # ==========================================
    # VISIBILITY CONTROL METHODS
    # ==========================================

    def show_grid(self, b_show=True):
        """
        Hiện/ẩn lưới (các shape có nhãn 'P').

        Args:
            b_show (bool): True để hiển thị, False để ẩn
        """
        shape: Shape = None
        for shape in self:
            if "P" in shape.label:
                if b_show:
                    shape.hide = False
                else:
                    shape.hide = True

    def change_hide(self):
        """Đảo trạng thái ẩn/hiện của shape được chọn."""
        index = self.idSelected
        s: Shape = None

        if index is not None:
            s: Shape = self[index]
            if s.hide:
                s.hide = False
            else:
                s.hide = True

    def change_hide_all(self):
        """Đảo trạng thái ẩn/hiện của tất cả các shapes."""
        s: Shape = None
        self.cancel_selected()
        if self.actions.hide_all.text() == "Hide All":
            self.actions.hide_all.setText("Show All")
            for s in self:
                s.hide = True
        else:
            self.actions.hide_all.setText("Hide All")
            for s in self:
                s.hide = False

    def change_lock(self):
        """Đảo trạng thái khóa của shape được chọn."""
        index = self.idSelected
        s: Shape = None

        if index is not None:
            s: Shape = self[index]
            if s.lock:
                s.lock = False
            else:
                s.lock = True

    def change_lock_all(self):
        """Đảo trạng thái khóa của tất cả các shapes."""
        s: Shape = None

        if self.actions.lock_all.text() == "Lock All":
            self.actions.lock_all.setText("UnLock All")
            for s in self:
                s.lock = True
        else:
            self.actions.lock_all.setText("Lock All")
            for s in self:
                s.lock = False

    def set_benable_drawing(self, enable):
        """
        Đặt trạng thái cho phép vẽ.

        Args:
            enable (bool): True để cho phép vẽ, False để không cho phép
        """
        self.benable_drawing = enable
        if self.benable_drawing:
            self.actions.disable_drawing.setText("Disable drawing")
        else:
            self.actions.disable_drawing.setText("Enable drawing")

    # ==========================================
    # MENU AND ACTION METHODS
    # ==========================================

    def setEnabledActions(self, enable):
        """
        Bật/tắt các actions trong menu.

        Args:
            enable (bool): True để bật, False để tắt
        """
        self.actions.copy.setEnabled(enable)
        self.actions.edit.setEnabled(enable)
        self.actions.delete.setEnabled(enable)
        self.actions.delete_all.setEnabled(enable)
        self.actions.lock.setEnabled(enable)

    def popUpMenu(self):
        """Hiển thị menu ngữ cảnh tại vị trí chuột."""
        if self.idSelected is None:
            self.setEnabledActions(False)
        else:
            self.setEnabledActions(True)
            s: Shape = self[self.idSelected]
            if s.lock:
                self.actions.lock.setText("UnLock")
            else:
                self.actions.lock.setText("Lock")

        if self.bcontext_menu:
            self.contextMenu.exec_(QCursor.pos())

    def emitAction(self, name):
        """
        Phát signal action với tên tương ứng.

        Args:
            name (str): Tên của action
        """
        self.actionSignal.emit(name)

    # ==========================================
    # POSITION AND TRANSFORMATION METHODS
    # ==========================================

    def focus_cursor(self):
        """Lấy vị trí của con trỏ trong hệ tọa độ canvas."""
        cur_pos = self.mapFromGlobal(QCursor().pos())
        return self.transformPos(cur_pos)

    def offset_center(self):
        """
        Tính toán vị trí để căn giữa hình ảnh trong khung nhìn.

        Returns:
            QPointF: Vị trí để căn giữa
        """
        dx = self.width() - self.picture.width() * self.scale
        dy = self.height() - self.picture.height() * self.scale
        pos = QPointF(dx / 2, dy / 2)
        self.org = pos
        return pos

    def transformPos(self, pos):
        """
        Chuyển đổi vị trí từ hệ tọa độ giao diện sang hệ tọa độ canvas.

        Args:
            pos (QPointF): Vị trí trong hệ tọa độ giao diện

        Returns:
            QPointF: Vị trí trong hệ tọa độ canvas
        """
        return (pos - self.org) / (self.scale + 1e-5)

    def move_org(self, point):
        """
        Di chuyển gốc tọa độ hiển thị.

        Args:
            point (QPointF): Vector di chuyển
        """
        self.org += point

    def shape_to_cvRect(self, shape):
        """
        Chuyển đổi một shape thành hình chữ nhật OpenCV (x, y, w, h).

        Args:
            shape (Shape): Shape cần chuyển đổi

        Returns:
            tuple: Hình chữ nhật dạng (x, y, w, h)
        """
        p1 = shape.points[0]
        p2 = shape.points[2]
        x, y = p1.x(), p1.y()
        x2, y2 = p2.x(), p2.y()

        # Giới hạn trong kích thước của ảnh
        x = max(x, 0)
        y = max(y, 0)
        x2 = min(x2, self.picture.width())
        y2 = min(y2, self.picture.height())

        # Chuyển về (x, y, w, h)
        w, h = int(x2 - x), int(y2 - y)
        x, y = int(x), int(y)

        return (x, y, w, h)

    # ==========================================
    # SHAPE MANAGEMENT METHODS
    # ==========================================

    def editShape(self):
        """Chỉnh sửa nhãn của shape được chọn."""
        if self.idSelected is not None:
            label = self.boxEditLabel.popUp(self.last_label, self.labels, bMove=True)
            if label:
                self[self.idSelected].label = label
                self.last_label = label
                self.append_new_label(label)

    def copyShape(self):
        """Tạo bản sao của shape được chọn."""
        if self.idSelected is not None:
            shape = self[self.idSelected].copy()
            self.shapes.append(shape)
            i = self.idSelected
            self.idSelected = i + 1

    def undo(self):
        """Hoàn tác thao tác cuối (xóa shape cuối)."""
        if len(self.shapes) > 0:
            self.shapes.remove(self[-1])

    def deleteShape(self):
        """Xóa shape được chọn."""
        if self.idSelected is not None:
            shape = self[self.idSelected]
            self.deleteShapeSignal.emit(self.idSelected)
            self.shapes.remove(shape)

            # Reset các chỉ số
            self.idVisible = self.idSelected = self.idCorner = None

    def delete_all(self):
        """Xóa tất cả các shapes."""
        for i in range(len(self)):
            self.deleteShapeSignal.emit(len(self) - 1)
            self.shapes.remove(self.shapes[-1])
        self.idVisible = self.idSelected = self.idCorner = None

    def moveShape(self, i, v):
        """
        Di chuyển shape theo vector.

        Args:
            i (int): Chỉ số của shape
            v (QPointF): Vector di chuyển
        """
        if self.picture is None:
            return
        self[i].move(v)
        self.moveShapeSignal.emit(i)

    def append_new_label(self, label):
        """
        Thêm nhãn mới vào danh sách và lưu vào file.

        Args:
            label (str): Nhãn cần thêm
        """
        if label not in self.labels:
            self.labels.append(label)
            self.labels = [lb.strip("\r\n") for lb in self.labels]
            string = "\n".join(self.labels)
            if os.path.exists(self.label_path):
                with open(self.label_path, "w") as ff:
                    ff.write(string)

    def newShape(self, r, label):
        """
        Tạo shape mới với hình chữ nhật và nhãn cho trước.

        Args:
            r (QRectF): Hình chữ nhật
            label (str): Nhãn của shape

        Returns:
            Shape: Shape mới được tạo
        """
        labels = [s.label for s in self.shapes]
        if label in labels:
            QMessageBox.warning(self, "WARNING", "Shape already exists")
            return

        shape = Shape(label)
        ret, points = shape.get_points(r)
        if ret:
            shape.points = points
            self.shapes.append(shape)
            self.newShapeSignal.emit(len(self) - 1)
            self.last_label = label
            self.append_new_label(label)
        return shape

    def format_shape(self, shape):
        """
        Định dạng shape thành dữ liệu cấu trúc.

        Args:
            shape (Shape): Shape cần định dạng

        Returns:
            dict: Dữ liệu có cấu trúc của shape
        """
        label = shape.label
        r = self.shape_to_cvRect(shape)
        id = self.shapes.index(shape)
        return {"label": label, "box": r, "id": id}

    # ==========================================
    # SHAPE SELECTION AND DETECTION METHODS
    # ==========================================

    def visibleShape(self, pos):
        """
        Xác định shape chứa vị trí pos (shape dưới con trỏ).

        Args:
            pos (QPointF): Vị trí cần kiểm tra

        Returns:
            int: Chỉ số của shape chứa pos hoặc None
        """
        n = len(self)
        ids_shape_contain_pos = []
        distances = []
        for i in range(n):
            self[i].visible = False
            d = self[i].dis_to(pos)
            if d > 0:
                ids_shape_contain_pos.append(i)
                distances.append(d)

        if len(distances) > 0:
            index = np.argmin(distances)
            self.idVisible = ids_shape_contain_pos[index]
            self[self.idVisible].visible = True
        else:
            self.idVisible = None
        return self.idVisible

    def selectedShape(self, pos):
        """
        Chọn shape tại vị trí pos.

        Args:
            pos (QPointF): Vị trí cần kiểm tra
        """
        ids_shape_contain_pos = []
        distances = []

        s: Shape = None
        for i, s in enumerate(self.shapes):
            if not s.hide:
                s.selected = False
                d = s.dis_to(pos)
                if d > 0:
                    ids_shape_contain_pos.append(i)
                    distances.append(d)

        if len(distances) > 0:
            index = np.argmin(distances)
            self.idSelected = ids_shape_contain_pos[index]
            self[self.idSelected].selected = True
            self.selectedShapeSignal.emit(self.idSelected)
        else:
            self.idSelected = None

    def highlightCorner(self, pos, epsilon=10):
        """
        Kiểm tra xem pos có gần với góc của shape được chọn hay không.

        Args:
            pos (QPointF): Vị trí cần kiểm tra
            epsilon (int, optional): Ngưỡng khoảng cách. Defaults to 10.

        Returns:
            bool: True nếu pos gần với một góc
        """
        if self.idSelected is None:
            return False
        try:
            i = self.idSelected
            return self[i].get_corner(pos, epsilon)
        except Exception as ex:
            print("{}".format(ex))
            return False

    def cancel_edit(self):
        """Hủy chế độ chỉnh sửa."""
        self.edit = False
        self.drawing = False
        self.moving = False

    def cancel_selected(self):
        """Hủy chọn tất cả shapes."""
        n = len(self)
        for i in range(n):
            self[i].selected = False
            self[i].corner = None
            self[i].visible = False
        self.idSelected = None

    # ==========================================
    # ZOOM AND VIEW CONTROL METHODS
    # ==========================================

    def active_edit(self):
        """Kích hoạt chế độ chỉnh sửa."""
        self.edit = True

    def on_show_full_screen(self):
        """Chuyển đổi chế độ toàn màn hình."""
        if not self._b_full_screen:
            self.show_full_screen()
        else:
            self.cancel_full_screen()

    def show_full_screen(self):
        """Hiển thị ở chế độ toàn màn hình."""
        self._b_full_screen = True
        self._old_parent = self.parent()
        self._geometry = self.saveGeometry()
        self.setParent(None)
        self.showFullScreen()
        self.tool_buttons[4].setIcon(newIcon("full_screen_off"))
        self.tool_buttons[4].setToolTip("Full screen off")

    def cancel_full_screen(self):
        """Hủy chế độ toàn màn hình."""
        self._b_full_screen = False
        self.setParent(self._old_parent)
        self.parent().setCentralWidget(self)
        self.tool_buttons[4].setIcon(newIcon("full_screen"))
        self.tool_buttons[4].setToolTip("Full screen")

    def fit_window(self):
        """Điều chỉnh tỉ lệ để vừa với cửa sổ."""
        if self.picture is None:
            return
        self.scale = self.scaleFitWindow()
        self.org = self.offset_center()

    def scaleFitWindow(self):
        """
        Tính tỉ lệ để vừa với cửa sổ.

        Returns:
            float: Tỉ lệ phù hợp
        """
        e = 2.0
        w1 = self.width() - 2
        h1 = self.height() - 2
        a1 = w1 / h1
        w2 = self.picture.width()
        h2 = self.picture.height()
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def zoom_origin(self):
        """Đặt tỉ lệ zoom về 1."""
        self.scale = 1
        self.org = QPointF()

    def zoom_manual(self, s):
        """
        Zoom theo hệ số s.

        Args:
            s (float): Hệ số zoom
        """
        self.scale *= s
        self.zoomSignal.emit(self.scale)
        return

    def zoom_focus_cursor(self, s):
        """
        Zoom vào tâm là vị trí con trỏ với hệ số s.

        Args:
            s (float): Hệ số zoom
        """
        old_scale = self.scale
        p1 = self.current_pos
        self.scale *= s
        # Điều chỉnh vị trí để con trỏ vẫn ở tâm
        self.org -= p1 * self.scale - p1 * old_scale

    def zoom_by_wheel(self, s):
        """
        Zoom bằng con lăn chuột với hệ số s.

        Args:
            s (float): Hệ số zoom
        """
        self.zoom_focus_cursor(s)
        self.zoomSignal.emit(self.scale)
        return

    def update_center(self, pos):
        """
        Cập nhật tâm hiển thị.

        Args:
            pos (QPointF): Tâm mới
        """
        pass

    def draw_rect(self, pos1, pos2):
        """
        Vẽ hình chữ nhật từ pos1 đến pos2.

        Args:
            pos1, pos2 (QPointF): Hai điểm đối diện của hình chữ nhật
        """
        self.current_rect = QRectF(pos1, pos2)

    # ==========================================
    # CURSOR HANDLING METHODS
    # ==========================================

    def currentCursor(self):
        """
        Lấy cursor hiện tại.

        Returns:
            Qt.CursorShape: Hình dạng của cursor
        """
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def overrideCursor(self, cursor):
        """
        Ghi đè cursor.

        Args:
            cursor (Qt.CursorShape): Hình dạng cursor mới
        """
        self._cursor = cursor
        if self.currentCursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    def restore_cursor(self):
        """Khôi phục cursor về mặc định."""
        QApplication.restoreOverrideCursor()

    def current_cursor(self):
        """
        Lấy cursor hiện tại.

        Returns:
            Qt.CursorShape: Hình dạng của cursor
        """
        cursor = QApplication.overrideCursor()
        if cursor is not None:
            cursor = cursor.shape()
        return cursor

    def override_cursor(self, cursor):
        """
        Ghi đè cursor.

        Args:
            cursor (Qt.CursorShape): Hình dạng cursor mới
        """
        self._cursor = cursor
        if self.current_cursor() is None:
            QApplication.setOverrideCursor(cursor)
        else:
            QApplication.changeOverrideCursor(cursor)

    # ==========================================
    # EVENT HANDLING METHODS
    # ==========================================

    def paintEvent(self, event):
        """
        Sự kiện vẽ lại canvas.

        Args:
            event (QPaintEvent): Sự kiện vẽ
        """
        r: QRect = self.geometry()
        self.label_pos.setGeometry(0, r.height() - 30, r.width(), 30)

        # toolbar_width = 50
        # self.tool_bar.setGeometry(0, 0, toolbar_width, r.height())
        toolbar_height = 30
        self.tool_bar.setGeometry(0, 0, r.width(), toolbar_height)

        if self.picture is None:
            return super(Canvas, self).paintEvent(event)

        p: QPainter = self.painter
        p.begin(self)
        lw = max(int(Shape.THICKNESS / (self.scale + 1e-5)), 1)
        p.setPen(QPen(Qt.green, lw))
        p.translate(self.org)
        p.scale(self.scale, self.scale)

        if self.picture:
            p.drawPixmap(0, 0, self.picture)

        shape: Shape = None
        for shape in self.shapes:
            shape.paint(p, self.scale)

        if self.edit:
            # Vẽ đường tâm
            pos = self.current_pos
            self.line1 = [QPointF(0, pos.y()), QPointF(self.picture.width(), pos.y())]
            self.line2 = [QPointF(pos.x(), 0), QPointF(pos.x(), self.picture.height())]
            p.drawLine(self.line1[0], self.line1[1])
            p.drawLine(self.line2[0], self.line2[1])

        if self.drawing:  # Vẽ hình chữ nhật
            if self.current is not None:
                p.drawRect(self.current)

        self.update()
        p.end()

        return super().paintEvent(event)

    def wheelEvent(self, ev):
        """
        Xử lý sự kiện con lăn chuột.

        Args:
            ev (QWheelEvent): Sự kiện con lăn chuột
        """
        if self.picture is None:
            return super(Canvas, self).wheelEvent(ev)
        delta = ev.angleDelta()
        h_delta = delta.x()
        v_delta = delta.y()
        mods = ev.modifiers()
        # if Qt.ControlModifier == int(mods) and v_delta:
        if v_delta:
            self.zoom_by_wheel(1 + v_delta / 120 * 0.2)
        # else:
        #     pos = QPointF(0.,v_delta/8.)
        #     self.move_org(pos)
        #     pass

        ev.accept()

    def mousePressEvent(self, ev):
        """
        Xử lý sự kiện nhấn chuột.

        Args:
            ev (QMouseEvent): Sự kiện nhấn chuột
        """
        if self.picture is None:
            return super(Canvas, self).mousePressEvent(ev)
        # pos = self.transformPos(ev.pos())
        self.start_pos = self.transformPos(ev.pos())
        if ev.button() == Qt.LeftButton:
            if self.edit:
                if self.idSelected is not None:
                    self[self.idSelected].selected = False
                    self.idSelected = None
                self.drawing = True
            else:
                self.moving = True
                if not self.highlight:
                    self.selectedShape(self.start_pos)

    def mouseReleaseEvent(self, ev):
        """
        Xử lý sự kiện thả chuột.

        Args:
            ev (QMouseEvent): Sự kiện thả chuột
        """
        if self.picture is None:
            return super(Canvas, self).mouseReleaseEvent(ev)
        # pos = self.transformPos(ev.pos())
        self.move_shape = False
        if ev.button() == Qt.LeftButton:
            if self.drawing:
                r = self.current
                if (
                    r is not None
                    and r.width() > Shape.MIN_WIDTH
                    and r.height() > Shape.MIN_WIDTH
                ):
                    label = self.boxEditLabel.popUp(
                        self.last_label, self.labels, bMove=False
                    )
                    if label:
                        self.newShape(r, label)
                self.current = None

            self.cancel_edit()

    def mouseMoveEvent(self, ev):
        """
        Xử lý sự kiện di chuyển chuột.

        Args:
            ev (QMouseEvent): Sự kiện di chuyển chuột
        """
        if self.picture is None:
            return super(Canvas, self).mouseMoveEvent(ev)

        self.current_pos: QPointF = self.transformPos(ev.pos())

        # Hiển thị thông tin pixel
        image = self.picture.toImage()
        try:
            pos: QPoint = self.current_pos.toPoint()
            if (
                self.picture.width() > pos.x() >= 0
                and self.picture.height() > pos.y() >= 0
            ):
                pixel: QColor = image.pixelColor(pos)
                h, s, v, _ = pixel.getHsv()
                r, g, b, _ = pixel.getRgb()
                x, y = pos.x(), pos.y()
                self.text_pixel_color = (
                    "POS: [%d, %d], BGR: [%d, %d, %d], HSV: [%d, %d, %d]"
                    % (x, y, b, g, r, h, s, v)
                )
                self.label_pos.setText(self.text_pixel_color)
        except Exception as ex:
            pass

        self.mouseMoveSignal.emit(self.current_pos)

        # Xử lý vẽ
        if self.drawing:
            self.current = QRectF(self.start_pos, self.current_pos)
            self.drawShapeSignal.emit(self.current)
            # self.override_cursor(CURSOR_MOVE)

        # Xử lý highlight
        if not self.moving:
            self.highlight = self.highlightCorner(self.current_pos, epsilon=40)
            if self.highlight:
                # self.override_cursor(CURSOR_DRAW)
                pass

        # Xử lý di chuyển
        if self.moving:
            v = self.current_pos - self.start_pos
            index = self.idSelected
            s: Shape = None
            if index is not None and not self[index].lock:
                s = self[index]
                if self.highlight:
                    s.change(v)
                else:
                    s.move(v)
            else:
                self.move_org(v * self.scale)

            self.start_pos = self.transformPos(ev.pos())
            if self.idSelected is not None:
                self.changeShapeSignal.emit(self.idSelected)
            # self.override_cursor(CURSOR_MOVE)

        # Xử lý cursor
        if (
            self.visibleShape(self.current_pos) is None
            and not self.highlight
            and not self.drawing
        ):
            self.restore_cursor()
        elif not self.highlight and not self.drawing and not self.moving:
            pass
            # self.override_cursor(CURSOR_GRAB)
        if self.edit:
            pass
            # self.restore_cursor()

    def keyPressEvent(self, ev):
        """
        Xử lý sự kiện nhấn phím.

        Args:
            ev (QKeyEvent): Sự kiện nhấn phím
        """
        key = ev.key()
        step = 5
        # if key == Qt.Key_1:
        #     self.parent.io_signal = not self.parent.io_signal
        if key == Qt.Key_W:
            if self.benable_drawing:
                self.edit = True

        elif key == Qt.Key_Escape:
            self.cancel_edit()
            self.cancel_selected()
            if self._b_full_screen:
                self.cancel_full_screen()

        elif key == Qt.Key_Delete:
            self.deleteShape()

        elif key == Qt.Key_Return:
            self.fit_window()

        elif key == Qt.Key_Plus:
            s = 1.2
            self.zoom_focus_cursor(s)

        elif key == Qt.Key_Minus:
            s = 0.8
            self.zoom_focus_cursor(s)

        i = self.idSelected
        if i is not None:
            if key == Qt.Key_Right:
                v = QPointF(step, 0)
                self.moveShape(i, v)
            elif key == Qt.Key_Left:
                v = QPointF(-step, 0)
                self.moveShape(i, v)
            elif key == Qt.Key_Up:
                v = QPointF(0, -step)
                self.moveShape(i, v)
            elif key == Qt.Key_Down:
                v = QPointF(0, step)
                self.moveShape(i, v)

        else:
            if self.picture is not None:
                step = min(self.picture.width() // 20, 10)
            else:
                step = 10

            if key == Qt.Key_Right:
                v = QPointF(step, 0)
                self.move_org(v)
            elif key == Qt.Key_Left:
                v = QPointF(-step, 0)
                self.move_org(v)
            elif key == Qt.Key_Up:
                v = QPointF(0, -step)
                self.move_org(v)
            elif key == Qt.Key_Down:
                v = QPointF(0, step)
                self.move_org(v)

    def resizeEvent(self, ev):
        """
        Xử lý sự kiện thay đổi kích thước.

        Args:
            ev (QResizeEvent): Sự kiện thay đổi kích thước
        """
        if self.picture is None:
            return super(Canvas, self).resizeEvent(ev)
        self.fit_window()

    # ==========================================
    # IMAGE LOADING METHODS
    # ==========================================

    def load_pixmap(self, pixmap, fit=False):
        """
        Tải pixmap lên canvas.

        Args:
            pixmap (QPixmap): Pixmap cần tải
            fit (bool, optional): True để fit vào cửa sổ. Defaults to False.
        """
        self.picture = pixmap
        if fit:
            self.fit_window()
        self.zoomSignal.emit(self.scale)
        self.repaint()

    def clear_pixmap(self):
        """Xóa pixmap hiện tại."""
        self.picture = None

    def clear(self):
        """Xóa tất cả shapes và reset trạng thái."""
        self.shapes.clear()
        self.idSelected = None
        self.idVisible = None
        self.idCorner = None

    # ==========================================
    # CONTAINER BEHAVIOR IMPLEMENTATION
    # ==========================================

    def __len__(self):
        """Trả về số lượng shapes."""
        return len(self.shapes)

    def __getitem__(self, key):
        """Truy cập shape theo chỉ số."""
        return self.shapes[key]

    def __setitem__(self, key, value):
        """Thiết lập shape theo chỉ số."""
        self.shapes[key] = value


class WindowCanvas(QMainWindow):
    """Cửa sổ chứa canvas."""

    def __init__(self, canvas=None, parent=None):
        super().__init__(parent=parent)
        self.setCentralWidget(canvas)
        self.setObjectName("WindowCanvas")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)
    # wd = QMainWindow()

    canvas = Canvas()
    canvas.load_pixmap(QPixmap(640, 480))

    # wd.setCentralWidget(canvas)
    canvas.showMaximized()

    sys.exit(app.exec_())
