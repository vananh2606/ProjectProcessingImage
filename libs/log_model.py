from PyQt5.QtCore import QAbstractListModel, Qt, QModelIndex, QDateTime, pyqtSignal
from PyQt5.QtGui import QColor, QBrush


class LogEntry:
    def __init__(self, message, level="INFO"):
        self.timestamp = QDateTime.currentDateTime()
        self.message = message
        self.level = level  # INFO, WARNING, ERROR, SUCCESS

    def __str__(self):
        time_str = self.timestamp.toString("yyyy-MM-dd hh:mm:ss")
        return f"[{time_str}] [{self.level}] {self.message}"


class LogModel(QAbstractListModel):
    layoutChangedLog = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.log_entries = []

        # Định nghĩa màu cho các loại log bằng QColor thay vì GlobalColor
        self.level_colors = {
            "INFO": QColor(0, 0, 0),  # Đen
            "WARNING": QColor(184, 134, 11),  # DarkGoldenrod
            "ERROR": QColor(178, 34, 34),  # Firebrick
            "SUCCESS": QColor(0, 100, 0),  # DarkGreen
        }

    def rowCount(self, parent=QModelIndex()):
        return len(self.log_entries)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or index.row() >= len(self.log_entries):
            return None

        entry = self.log_entries[index.row()]

        if role == Qt.ItemDataRole.DisplayRole:
            return str(entry)
        elif role == Qt.ItemDataRole.ForegroundRole:
            # Trả về QBrush với màu sắc phù hợp
            color = self.level_colors.get(entry.level, QColor(0, 0, 0))
            return QBrush(color)
        elif role == Qt.ItemDataRole.ToolTipRole:
            # Thêm tooltip hiển thị khi hover
            return f"Level: {entry.level}\nTime: {entry.timestamp.toString()}\nMessage: {entry.message}"

        return None

    def add_log(self, message, level="INFO"):
        """Thêm log mới vào model"""
        self.beginInsertRows(
            QModelIndex(), len(self.log_entries), len(self.log_entries)
        )
        self.log_entries.append(LogEntry(message, level))
        self.endInsertRows()
        self.layoutChangedLog.emit()

    def add_info(self, message):
        """Thêm log thông tin"""
        self.add_log(message, "INFO")

    def add_warning(self, message):
        """Thêm log cảnh báo"""
        self.add_log(message, "WARNING")

    def add_error(self, message):
        """Thêm log lỗi"""
        self.add_log(message, "ERROR")

    def add_success(self, message):
        """Thêm log thành công"""
        self.add_log(message, "SUCCESS")

    def clear(self):
        """Xóa tất cả logs"""
        self.beginResetModel()
        self.log_entries.clear()
        self.endResetModel()
