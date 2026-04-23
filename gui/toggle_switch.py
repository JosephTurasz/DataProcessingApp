from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen

class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checked = False
        self._track_margin = 2
        self._thumb_diameter = 16
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(36, 20)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool):
        checked = bool(checked)
        if self._checked == checked:
            return
        self._checked = checked
        self.update()
        self.toggled.emit(self._checked)

    def toggle(self):
        self.setChecked(not self._checked)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(1, 1, -1, -1)
        radius = rect.height() / 2

        track_off = QColor("#6b7280")
        track_on = QColor("#22c55e")
        border_off = QColor("#4b5563")
        border_on = QColor("#16a34a")
        thumb = QColor("#ffffff")

        painter.setPen(QPen(border_on if self._checked else border_off, 1))
        painter.setBrush(track_on if self._checked else track_off)
        painter.drawRoundedRect(rect, radius, radius)

        y = (self.height() - self._thumb_diameter) / 2
        x = (self.width() - self._thumb_diameter - self._track_margin if self._checked else self._track_margin)

        painter.setPen(QPen(QColor("#d1d5db"), 1))
        painter.setBrush(thumb)
        painter.drawEllipse(QRectF(x, y, self._thumb_diameter, self._thumb_diameter))
        painter.end()
