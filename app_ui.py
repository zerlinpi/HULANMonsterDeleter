import base64

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QWidget

from delete_engine import DELETE_MODE
from embedded_photos import PHOTO_CLOSE_B64


def portrait_card(target_height: int = 88, radius: int = 22) -> QPixmap:
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(PHOTO_CLOSE_B64))
    if pixmap.isNull():
        return pixmap
    w, h = pixmap.width(), pixmap.height()
    x, y, cw, ch = int(w * 0.07), int(h * 0.03), int(w * 0.86), int(h * 0.94)
    cropped = pixmap.copy(x, y, min(cw, w - x), min(ch, h - y))
    scaled = cropped.scaledToHeight(target_height, Qt.TransformationMode.SmoothTransformation)

    card = QPixmap(scaled.width() + 8, scaled.height() + 8)
    card.fill(Qt.GlobalColor.transparent)
    painter = QPainter(card)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(4, 4, scaled.width(), scaled.height())
    clip = QPainterPath()
    clip.addRoundedRect(rect, radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(4, 4, scaled)
    painter.setClipping(False)
    painter.setPen(QPen(QColor(255, 255, 255, 210), 3))
    painter.drawRoundedRect(rect, radius, radius)
    painter.end()
    return card


class BubbleWidget(QWidget):
    def __init__(self, text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        row = QHBoxLayout()
        row.setContentsMargins(18, 12, 18, 24)
        row.setSpacing(12)
        self.avatar = QLabel()
        avatar = portrait_card()
        if not avatar.isNull():
            self.avatar.setPixmap(avatar)
            self.avatar.setFixedSize(avatar.size())
        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setMaximumWidth(440)
        self.lbl_text.setStyleSheet("QLabel{color:#1c1c1e;font-family:'Segoe UI','Microsoft YaHei';font-size:17px;font-weight:600;}")
        row.addWidget(self.avatar)
        row.addWidget(self.lbl_text)
        self.setLayout(row)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

    def set_text(self, text: str) -> None:
        self.lbl_text.setText(text)
        self.adjustSize()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 246))
        rect = self.rect()
        path = QPainterPath()
        path.addRoundedRect(0, 0, float(rect.width()), float(max(1, rect.height() - 14)), 22.0, 22.0)
        tail = QPainterPath()
        tail.moveTo(float(rect.width()) / 2 - 14, float(rect.height() - 14))
        tail.lineTo(float(rect.width()) / 2, float(rect.height()))
        tail.lineTo(float(rect.width()) / 2 + 14, float(rect.height() - 14))
        path.addPath(tail)
        painter.drawPath(path)


class ChoicesWidget(QWidget):
    choiceMade = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QHBoxLayout()
        layout.setSpacing(12)
        self.confirm = QPushButton("永久删除")
        self.cancel = QPushButton("取消")
        style = """
        QPushButton{background-color:rgba(255,255,255,245);color:#1c1c1e;border:1px solid #d1d1d6;border-radius:16px;
        padding:10px 22px;font-family:'Segoe UI','Microsoft YaHei';font-size:15px;font-weight:600;}
        QPushButton:hover{background-color:#007aff;color:white;border-color:#007aff;}
        QPushButton:pressed{background-color:#005bb5;color:white;}
        """
        self.confirm.setStyleSheet(style)
        self.cancel.setStyleSheet(style)
        self.confirm.clicked.connect(lambda: self.choiceMade.emit(True))
        self.cancel.clicked.connect(lambda: self.choiceMade.emit(False))
        layout.addWidget(self.confirm)
        layout.addWidget(self.cancel)
        self.setLayout(layout)

    def configure(self, has_target: bool) -> None:
        if not has_target:
            self.confirm.setText("仅播放动画")
        elif DELETE_MODE == "permanent":
            self.confirm.setText("永久删除")
        else:
            self.confirm.setText("移入回收站")
