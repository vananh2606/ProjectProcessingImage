from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
import os
import time
import cv2

# ==========================================
# UI STYLE AND APPEARANCE
# ==========================================


def load_style_sheet(filename: str, widget: QWidget):
    """Tải stylesheet từ file và áp dụng lên widget."""
    file = QFile(filename)
    file.open(QFile.ReadOnly | QFile.Text)
    stream = file.readAll()
    widget.setStyleSheet(stream.data().decode("UTF-8"))


def update_style(item):
    item.style().unpolish(item)
    item.style().polish(item)


def newIcon(icon_name):
    """Tạo QIcon từ tên resource."""
    return QIcon(":/" + icon_name)


# ==========================================
# BASIC WIDGETS CREATION
# ==========================================


def newLabel(text, style="", align=None):
    """Tạo QLabel với style và alignment tùy chọn."""
    lb = QLabel(text)
    if style:
        lb.setStyleSheet(style)
    if align:
        lb.setAlignment(align)
    return lb


def newButton(text, parent=None, slot=None, icon=None, enabled=True):
    """Tạo QPushButton với các thuộc tính tùy chọn."""
    btn = QPushButton(text, parent)
    if slot is not None:
        btn.clicked.connect(slot)
    if icon is not None:
        btn.setIcon(newIcon(icon))
    btn.setEnabled(enabled)
    return btn


def newToolButton(action, parent=None, style=Qt.ToolButtonTextUnderIcon):
    """Tạo QToolButton dựa trên QAction."""
    b = QToolButton(parent)
    b.setToolButtonStyle(style)
    b.setDefaultAction(action)
    return b


def newCheckBox(text, slot=None, state=False, tooltip=""):
    """Tạo QCheckBox với các thuộc tính tùy chọn."""
    ch = QCheckBox(text)
    ch.setChecked(state)
    if slot is not None:
        ch.stateChanged.connect(slot)
    if tooltip:
        ch.setToolTip(tooltip)
    return ch


def newRadioButton(text, slot=None, state=False):
    """Tạo QRadioButton với các thuộc tính tùy chọn."""
    rad = QRadioButton(text)
    if slot is not None:
        rad.clicked.connect(slot)
    rad.setChecked(state)
    return rad


def newComboBox(items, parent=None, slot=None):
    """Tạo QComboBox với danh sách items."""
    cbb = QComboBox(parent)
    [cbb.addItem(str(item)) for item in items]
    if slot is not None:
        cbb.currentIndexChanged.connect(slot)
    return cbb


def newSlider(_range=(0, 255), value=0, step=1, slot=None):
    """Tạo QSlider với giá trị và range tùy chọn."""
    sl = QSlider(Qt.Horizontal)
    a, b = _range
    sl.setRange(a, b)
    sl.setValue(value)
    sl.setSingleStep(step)
    if slot is not None:
        sl.valueChanged.connect(slot)
    return sl


def newSpinbox(range_, value, step=1, slot=None):
    """Tạo QSpinBox với giá trị và range tùy chọn."""
    sp = QSpinBox()
    a, b = range_
    sp.setRange(a, b)
    sp.setValue(value)
    sp.setSingleStep(step)
    if slot:
        sp.valueChanged.connect(slot)
    return sp


def newDoubleSpinbox(range_, value, step=1, slot=None):
    """Tạo QDoubleSpinBox với giá trị và range tùy chọn."""
    sp = QDoubleSpinBox()
    sp.setValue(value)
    a, b = range_
    sp.setRange(a, b)
    sp.setSingleStep(step)
    if slot:
        sp.valueChanged.connect(slot)
    return sp


def newTabWidget(parent=None, position=QTabWidget.North):
    """Tạo QTabWidget với vị trí tabs tùy chọn."""
    tab = QTabWidget(parent)
    tab.setTabPosition(position)
    return tab


def newDialogButtonBox(parent):
    """Tạo QDialogButtonBox với nút OK và Cancel."""
    BB = QDialogButtonBox
    bb = BB(BB.Ok | BB.Cancel)
    bb.rejected.connect(parent.reject)
    bb.accepted.connect(parent.accept)
    return bb


# ==========================================
# LAYOUT MANAGEMENT
# ==========================================


def new_hlayout(widgets=[], stretchs=[], parent=None):
    """Tạo QHBoxLayout và thêm các widgets."""
    h = QHBoxLayout(parent)
    addWidgets(h, widgets, stretchs)
    return h


def new_vlayout(widgets=[], stretchs=[], parent=None):
    """Tạo QVBoxLayout và thêm các widgets."""
    v = QVBoxLayout(parent)
    addWidgets(v, widgets, stretchs)
    return v


def addWidgets(layout, widgets, stretchs=[]):
    """Thêm widgets vào layout với stretch factors."""
    for i, w in enumerate(widgets):
        if isinstance(w, QWidget):
            layout.addWidget(w)
        else:
            layout.addLayout(w)
        if stretchs and i < len(stretchs):
            if isinstance(layout, QSplitter):
                layout.setStretchFactor(i, stretchs[i])
            else:
                layout.setStretch(i, stretchs[i])


def addTabs(tab, widgets, names, icons=None):
    """Thêm tabs vào QTabWidget hoặc QToolBox."""
    if icons is not None:
        for w, name, ico in zip(widgets, names, icons):
            if isinstance(tab, QTabWidget):
                tab.addTab(w, newIcon(ico), name)
            elif isinstance(tab, QToolBox):
                tab.addItem(w, newIcon(ico), name)
    else:
        for w, name in zip(widgets, names):
            if isinstance(tab, QTabWidget):
                tab.addTab(w, name)
            elif isinstance(tab, QToolBox):
                tab.addItem(w, name)


def add_scroll(widget):
    """Đặt widget trong QScrollArea."""
    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    return scroll


def add_dock(
    parent: QMainWindow,
    text,
    object_name,
    widget,
    area=Qt.RightDockWidgetArea,
    feature=QDockWidget.NoDockWidgetFeatures,
    orient=None,
):
    """Thêm QDockWidget vào QMainWindow."""
    dock = QDockWidget(text, parent)
    dock.setObjectName(object_name)
    dock.setAllowedAreas(Qt.AllDockWidgetAreas)
    dock.setFeatures(feature)
    dock.setWidget(widget)
    if orient is not None:
        parent.addDockWidget(area, dock, orient)
    else:
        parent.addDockWidget(area, dock)
    return dock


# ==========================================
# ACTIONS AND MENUS
# ==========================================


def newAction(
    parent, text, slot=None, shortcut=None, icon=None, tooltip=None, enabled=True
):
    """Tạo QAction với các thuộc tính tùy chọn."""
    a = QAction(text, parent)
    if icon is not None:
        a.setIcon(newIcon(icon))
    if shortcut is not None:
        a.setShortcut(shortcut)
    if slot is not None:
        a.triggered.connect(slot)
    if tooltip is not None:
        a.setToolTip(tooltip)
    a.setEnabled(enabled)
    return a


def addActions(menu, actions):
    """Thêm danh sách actions vào menu."""
    for act in actions:
        if isinstance(act, QAction):
            menu.addAction(act)
        else:
            menu.addMenu(act)


def addTriggered(action, trigger):
    """Kết nối triggered signal của action với slot."""
    action.triggered.connect(trigger)


def add_context_menu(parent, widget, actions, popup_function=None):
    """Tạo menu ngữ cảnh cho widget."""
    menu = QMenu(parent)
    addActions(menu, actions)
    widget.setContextMenuPolicy(Qt.CustomContextMenu)
    if popup_function is None:
        widget.customContextMenuRequested.connect(lambda: menu.exec_(QCursor.pos()))
    else:
        widget.customContextMenuRequested.connect(popup_function)
    return menu


def newDialogButton(parent, texts, slots, icons, orient=Qt.Vertical):
    """Tạo QDialogButtonBox với nhiều nút tùy chỉnh."""
    bb = QDialogButtonBox(orient, parent)
    for txt, slot, icon in zip(texts, slots, icons):
        but = bb.addButton("", QDialogButtonBox.ApplyRole)
        but.setToolTip(txt)
        if slot is not None:
            but.clicked.connect(slot)
        if icon is not None:
            but.setIcon(newIcon(icon))
    return bb


# ==========================================
# FILE DIALOGS
# ==========================================


def get_save_file_name_dialog(parent, base="", _filter_="Image files (*png *jpg *bmp)"):
    """Hiển thị hộp thoại lưu file."""
    options = QFileDialog.Options()
    filename, _ = QFileDialog.getSaveFileName(
        parent, "Save as", base, _filter_, options=options
    )
    return filename


def get_folder_name_dialog(parent, base=""):
    """Hiển thị hộp thoại chọn thư mục."""
    options = QFileDialog.Options()
    options |= QFileDialog.ShowDirsOnly
    folder = QFileDialog.getExistingDirectory(
        parent, "Select folder", base, options=options
    )
    return folder


def get_file_name_dialog(parent, base="", _filter_="Image files (*png *jpg *bmp)"):
    """Hiển thị hộp thoại mở file."""
    options = QFileDialog.Options()
    filename, _ = QFileDialog.getOpenFileName(
        parent, "Select file", base, _filter_, options=options
    )
    return filename


# ==========================================
# CUSTOM WIDGETS
# ==========================================


class BoxEditLabel(QDialog):
    """Hộp thoại chỉnh sửa nhãn."""

    def __init__(self, title="QDialog", parent=None):
        super(BoxEditLabel, self).__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout()

        bb = newDialogButtonBox(self)

        self.ln_name = QLineEdit()
        self.ln_name.setFocus()
        self.list_name = QListWidget()
        addWidgets(layout, [self.ln_name, bb, self.list_name])
        self.setLayout(layout)

        self.list_name.itemClicked.connect(self.itemClicked)
        self.list_name.itemDoubleClicked.connect(self.itemDoubleClicked)

    def itemClicked(self, item):
        self.ln_name.setText(item.text())

    def itemDoubleClicked(self, item):
        self.ln_name.setText(item.text())
        self.accept()

    def popUp(self, text="", names=[], bMove=False):
        self.list_name.clear()
        self.list_name.addItems(names)
        self.ln_name.setText(text)
        self.ln_name.setSelection(0, len(text))
        if bMove:
            self.move(QCursor.pos())
        return self.ln_name.text() if self.exec_() else ""


class ListWidget(QListWidget):
    """QListWidget mở rộng với menu ngữ cảnh và chức năng log."""

    def __init__(self, style=None, parent=None):
        super(ListWidget, self).__init__(parent)
        if style is not None:
            self.setStyleSheet(style)

        clear = newAction(self, "clear", self.clear, "ctrl+x")
        self.menu = add_context_menu(self, self, [clear])

    def addLog(self, log, color=None, reverse=False):
        if self.count() > 1000:
            self.clear()
        log = "%s : %s" % (time.strftime("%H:%M:%S"), str(log))
        if reverse:
            self.insertItem(0, log)
            if color is not None:
                self.item(0).setForeground(color)
        else:
            self.addItem(log)
            n = self.count()
            if color is not None:
                self.item(n - 1).setForeground(color)


class ToolBar(QToolBar):
    """QToolBar tùy chỉnh với layout và margins cụ thể."""

    def __init__(self, title):
        super(ToolBar, self).__init__(title)
        layout = self.layout()
        m = (0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setContentsMargins(*m)
        self.setContentsMargins(*m)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)

    def addAction(self, action):
        if isinstance(action, QWidgetAction):
            return super(ToolBar, self).addAction(action)
        btn = ToolButton()
        btn.setDefaultAction(action)
        btn.setToolButtonStyle(self.toolButtonStyle())
        self.addWidget(btn)


class ToolButton(QToolButton):
    """QToolButton tùy chỉnh đảm bảo tất cả các nút có cùng kích thước."""

    minSize = (60, 30)

    def minimumSizeHint(self):
        ms = super(ToolButton, self).minimumSizeHint()
        w1, h1 = ms.width(), ms.height()
        w2, h2 = self.minSize
        ToolButton.minSize = max(w1, w2), max(h1, h2)
        return QSize(*ToolButton.minSize)


class WindowMixin(object):
    """Mixin class để thêm chức năng menu và toolbar vào window."""

    def menu(self, title, actions=None) -> QMenu:
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None, orient=Qt.TopToolBarArea):
        toolbar = ToolBar(title)
        toolbar.setObjectName("%sToolBar" % title)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(orient, toolbar)
        return toolbar


class struct(object):
    """Lớp tiện ích để tạo đối tượng với các thuộc tính từ kwargs."""

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


# ==========================================
# IMAGE CONVERSION
# ==========================================


def ndarray2pixmap(arr):
    """Chuyển đổi numpy.ndarray thành QPixmap."""
    if len(arr.shape) == 2:
        rgb = cv2.cvtColor(arr, cv2.COLOR_GRAY2RGB)
    else:
        rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    h, w, channel = rgb.shape
    qimage = QImage(rgb.data, w, h, channel * w, QImage.Format_RGB888)
    pixmap = QPixmap.fromImage(qimage)
    return pixmap


# ==========================================
# RESOURCE MANAGEMENT
# ==========================================


def create_resources():
    """Tạo file resources.qrc từ thư mục icon và biên dịch thành resources.py."""
    cwd = os.getcwd()
    folder = "resources/icons"
    files = os.listdir(folder)
    top = ['<!DOCTYPE RCC><RCC version="1.0">', "<qresource>"]
    bot = ["</qresource>", "</RCC>"]
    for f in files:
        base, ext = os.path.splitext(f)
        alias = f'<file alias="%s">icon/%s</file>' % (base, f)
        top = top + [alias]
    resources = "\n".join(top + bot)
    with open("resources/resources.qrc", "w") as ff:
        ff.write(resources)

    os.system("pyrcc5 -o libs/resources.py resources/resources.qrc")


if __name__ == "__main__":
    create_resources()
