import base64
import os
import sys
import winreg

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QRectF, QTimer, Qt, QUrl, pyqtProperty, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QImage, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from delete_engine import DELETE_MODE, delete_path
from embedded_photos import PHOTO_CLOSE_B64, PHOTO_FULL_B64


def get_resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


ASSET_DIR = get_resource_path("assets")
COLS = 5
ROWS = 3


def register_context_menu() -> None:
    """Register per-user Explorer context-menu entries for files and folders."""
    try:
        exe_path = sys.executable
        if not exe_path.lower().endswith(".exe") or "python" in os.path.basename(exe_path).lower():
            script_path = os.path.abspath(__file__)
            command_str = f'"{exe_path}" "{script_path}" "%1"'
            icon_str = "shell32.dll,31"
        else:
            command_str = f'"{exe_path}" "%1"'
            icon_str = f'"{exe_path}",0'

        for key_path in (
            r"Software\Classes\*\shell\PhotoMonsterDelete",
            r"Software\Classes\Directory\shell\PhotoMonsterDelete",
        ):
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValue(key, "", winreg.REG_SZ, "召唤照片角色删除")
            winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, icon_str)
            winreg.CloseKey(key)

            command_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path + r"\command")
            winreg.SetValue(command_key, "", winreg.REG_SZ, command_str)
            winreg.CloseKey(command_key)
    except Exception as exc:
        print(f"Context-menu registration failed: {exc}")


def _load_embedded_pixmap(which: str) -> QPixmap:
    payload = PHOTO_CLOSE_B64 if which == "close" else PHOTO_FULL_B64
    pixmap = QPixmap()
    pixmap.loadFromData(base64.b64decode(payload))
    return pixmap


def _photo_crop(which: str) -> QPixmap:
    pixmap = _load_embedded_pixmap(which)
    if pixmap.isNull():
        return pixmap

    w, h = pixmap.width(), pixmap.height()
    if which == "close":
        # Close portrait: face + upper body from the second supplied photo.
        x, y, cw, ch = int(w * 0.07), int(h * 0.03), int(w * 0.86), int(h * 0.94)
    else:
        # Full-body crop from the first supplied photo; the V-sign remains visible.
        x, y, cw, ch = int(w * 0.05), int(h * 0.02), int(w * 0.90), int(h * 0.96)

    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    cw = max(1, min(cw, w - x))
    ch = max(1, min(ch, h - y))
    return pixmap.copy(x, y, cw, ch)


def _photo_card(which: str, target_height: int, radius: int = 28) -> QPixmap:
    cropped = _photo_crop(which)
    if cropped.isNull():
        return QPixmap()

    scaled = cropped.scaledToHeight(target_height, Qt.TransformationMode.SmoothTransformation)
    card = QPixmap(scaled.width() + 8, scaled.height() + 8)
    card.fill(Qt.GlobalColor.transparent)

    painter = QPainter(card)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    rect = QRectF(4, 4, scaled.width(), scaled.height())
    clip_path = QPainterPath()
    clip_path.addRoundedRect(rect, radius, radius)
    painter.setClipPath(clip_path)
    painter.drawPixmap(4, 4, scaled)
    painter.setClipping(False)
    painter.setPen(QPen(QColor(255, 255, 255, 210), 3))
    painter.drawRoundedRect(rect, radius, radius)
    painter.end()
    return card


def _animated_photo_frame(
    which: str,
    target_height: int,
    angle: float = 0.0,
    scale: float = 1.0,
    y_offset: int = 0,
    mirror: bool = False,
) -> QPixmap:
    card = _photo_card(which, target_height)
    if card.isNull():
        return card

    transform = QTransform()
    if mirror:
        transform.scale(-1, 1)
    transform.rotate(angle)
    transform.scale(scale, scale)
    transformed = card.transformed(transform, Qt.TransformationMode.SmoothTransformation)

    padding = 150
    canvas = QPixmap(card.width() + padding, card.height() + padding)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    x = (canvas.width() - transformed.width()) // 2
    y = (canvas.height() - transformed.height()) // 2 + y_offset
    painter.drawPixmap(x, y, transformed)
    painter.end()
    return canvas


class PhotoAnimator(QLabel):
    animationFinished = pyqtSignal()
    frameChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: list[QPixmap] = []
        self.current_frame = 0
        self.loop = True
        self.is_playing = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

    def load_animation(self, style: str, target_height: int = 430, mirror: bool = False) -> bool:
        patterns = {
            "walk": [(-2, 1.00, 7), (1, 1.02, 0), (2, 1.01, 5), (-1, 0.995, 1)],
            "point": [(-1, 1.00, 1), (0, 1.015, 0), (1, 1.00, 1), (0, 1.01, 0)],
            "kick": [(0, 1.00, 0), (-3, 1.03, 0), (-7, 1.08, -2), (5, 1.13, -5), (2, 1.06, 0), (0, 1.00, 2)],
            "idle": [(-1, 1.00, 2), (0, 1.012, 0), (1, 1.00, 2), (0, 1.008, 0)],
        }
        sequence = patterns.get(style, patterns["idle"])
        which = "close" if style == "idle" else "full"
        self.frames = [
            _animated_photo_frame(which, target_height, angle, scale, yoff, mirror)
            for angle, scale, yoff in sequence
        ]
        self.frames = [frame for frame in self.frames if not frame.isNull()]
        self.current_frame = 0
        if self.frames:
            self.resize(self.frames[0].size())
            self._update_frame()
            return True
        return False

    def play(self, fps: int = 8, loop: bool = True) -> None:
        if not self.frames:
            return
        self.loop = loop
        self.current_frame = 0
        self.is_playing = True
        self.timer.start(max(1, 1000 // fps))
        self._update_frame()

    def stop(self) -> None:
        self.timer.stop()
        self.is_playing = False

    def next_frame(self) -> None:
        if not self.frames:
            return
        self.current_frame += 1
        if self.current_frame >= len(self.frames):
            if self.loop:
                self.current_frame = 0
            else:
                self.current_frame = len(self.frames) - 1
                self.stop()
                self._update_frame()
                self.frameChanged.emit(self.current_frame)
                self.animationFinished.emit()
                return
        self._update_frame()
        self.frameChanged.emit(self.current_frame)

    def _update_frame(self) -> None:
        if self.frames:
            self.setPixmap(self.frames[self.current_frame])


class SpriteSheetAnimator(QLabel):
    animationFinished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: list[QPixmap] = []
        self.current_frame = 0
        self.loop = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

    def load_spritesheet(self, filepath: str, cols: int = COLS, rows: int = ROWS, target_height: int = 150) -> bool:
        transparent_path = filepath.replace(".png", "_transparent.png")
        if os.path.exists(transparent_path):
            filepath = transparent_path
        if not os.path.exists(filepath):
            return False

        image = QImage(filepath)
        if image.isNull():
            return False
        pixmap = QPixmap.fromImage(image)
        frame_w, frame_h = pixmap.width() // cols, pixmap.height() // rows
        self.frames = []
        for row in range(rows):
            for col in range(cols):
                frame = pixmap.copy(col * frame_w, row * frame_h, frame_w, frame_h)
                self.frames.append(frame.scaledToHeight(target_height, Qt.TransformationMode.SmoothTransformation))
        if self.frames:
            self.resize(self.frames[0].size())
            self.setPixmap(self.frames[0])
            return True
        return False

    def play(self, fps: int = 8, loop: bool = False) -> None:
        if not self.frames:
            return
        self.loop = loop
        self.current_frame = 0
        self.timer.start(max(1, 1000 // fps))

    def next_frame(self) -> None:
        if not self.frames:
            return
        self.current_frame += 1
        if self.current_frame >= len(self.frames):
            if self.loop:
                self.current_frame = 0
            else:
                self.current_frame = len(self.frames) - 1
                self.timer.stop()
                self.animationFinished.emit()
                return
        self.setPixmap(self.frames[self.current_frame])


class BubbleWidget(QWidget):
    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        row = QHBoxLayout()
        row.setContentsMargins(18, 12, 18, 24)
        row.setSpacing(12)

        self.avatar = QLabel()
        avatar_pix = _photo_card("close", 88, radius=22)
        self.avatar.setPixmap(avatar_pix)
        self.avatar.setFixedSize(avatar_pix.size())

        self.lbl_text = QLabel(text)
        self.lbl_text.setWordWrap(True)
        self.lbl_text.setStyleSheet(
            "QLabel { color:#1c1c1e; font-family:'Segoe UI','Microsoft YaHei'; font-size:17px; font-weight:600; }"
        )
        self.lbl_text.setMaximumWidth(420)

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
            QPushButton {
                background-color: rgba(255,255,255,245);
                color:#1c1c1e;
                border:1px solid #d1d1d6;
                border-radius:16px;
                padding:10px 22px;
                font-family:'Segoe UI','Microsoft YaHei';
                font-size:15px;
                font-weight:600;
            }
            QPushButton:hover { background-color:#007aff; color:white; border-color:#007aff; }
            QPushButton:pressed { background-color:#005bb5; color:white; }
        """
        self.confirm.setStyleSheet(style)
        self.cancel.setStyleSheet(style)
        self.confirm.clicked.connect(lambda: self.choiceMade.emit(True))
        self.cancel.clicked.connect(lambda: self.choiceMade.emit(False))
        layout.addWidget(self.confirm)
        layout.addWidget(self.cancel)
        self.setLayout(layout)

    def configure(self, has_target: bool) -> None:
        self.confirm.setText("永久删除" if has_target else "仅播放动画")


class MonsterDeleter(QWidget):
    def __init__(self, target_file: str | None):
        super().__init__()
        self.target_file = os.path.abspath(target_file) if target_file else None
        self.target_pos = None
        self._bg_opacity = 0.0
        self.sequence_started = False
        self.delete_result = ""

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(QApplication.primaryScreen().geometry())

        self.animator = PhotoAnimator(self)
        self.animator.hide()
        self.explosion_animator = SpriteSheetAnimator(self)
        self.explosion_animator.hide()
        self.bubble = BubbleWidget("")
        self.choices = ChoicesWidget()

        self.init_audio()
        self.init_targeting_ui()

    @pyqtProperty(float)
    def bg_opacity(self) -> float:
        return self._bg_opacity

    @bg_opacity.setter
    def bg_opacity(self, value: float) -> None:
        self._bg_opacity = value
        self.update()

    def init_audio(self) -> None:
        self.bgm_player = QMediaPlayer()
        self.bgm_audio = QAudioOutput()
        self.bgm_player.setAudioOutput(self.bgm_audio)
        self.bgm_audio.setVolume(0.45)

        self.sfx_player = QMediaPlayer()
        self.sfx_audio = QAudioOutput()
        self.sfx_player.setAudioOutput(self.sfx_audio)
        self.sfx_audio.setVolume(0.85)

        self.exp_player = QMediaPlayer()
        self.exp_audio = QAudioOutput()
        self.exp_player.setAudioOutput(self.exp_audio)
        self.exp_audio.setVolume(0.35)

        bgm_path = get_resource_path(r"assets\音频\bgm(1).mp3")
        speech_path = get_resource_path(r"assets\音频\怪兽说话.mp3")
        exp_path = get_resource_path(r"assets\音频\爆炸.MP4")
        if os.path.exists(bgm_path):
            self.bgm_player.setSource(QUrl.fromLocalFile(bgm_path))
            self.bgm_player.mediaStatusChanged.connect(self.loop_bgm)
        if os.path.exists(speech_path):
            self.sfx_player.setSource(QUrl.fromLocalFile(speech_path))
        if os.path.exists(exp_path):
            self.exp_player.setSource(QUrl.fromLocalFile(exp_path))

    def loop_bgm(self, status) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.bgm_player.setPosition(0)
            self.bgm_player.play()

    def init_targeting_ui(self) -> None:
        cursor_size = 40
        cursor_pixmap = QPixmap(cursor_size, cursor_size)
        cursor_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(cursor_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(255, 45, 45), 2))
        center, radius = cursor_size // 2, 12
        painter.drawEllipse(center - radius, center - radius, radius * 2, radius * 2)
        painter.drawLine(center, 0, center, center - 4)
        painter.drawLine(center, center + 4, center, cursor_size)
        painter.drawLine(0, center, center - 4, center)
        painter.drawLine(center + 4, center, cursor_size, center)
        painter.end()
        self.setCursor(QCursor(cursor_pixmap, center, center))

        self.fade_in_anim = QPropertyAnimation(self, b"bg_opacity")
        self.fade_in_anim.setDuration(500)
        self.fade_in_anim.setStartValue(0.0)
        self.fade_in_anim.setEndValue(0.38)
        self.fade_in_anim.start()

    def paintEvent(self, event) -> None:
        if self._bg_opacity <= 0.01:
            return
        painter = QPainter(self)
        painter.setOpacity(self._bg_opacity)
        painter.fillRect(self.rect(), QColor(10, 10, 12, 220))
        painter.setOpacity(min(1.0, self._bg_opacity / 0.38))
        painter.setPen(QColor(255, 255, 255))
        font = painter.font()
        font.setPointSize(24)
        font.setBold(True)
        painter.setFont(font)

        if self.target_file:
            filename = os.path.basename(self.target_file) or self.target_file
            text = f"点击屏幕上目标所在位置开始动画\n已锁定：{filename}"
        else:
            text = "演示模式：点击任意位置开始动画\n未通过右键菜单选择文件，因此不会删除任何内容"
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.on_app_exit()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if not self.sequence_started and event.button() == Qt.MouseButton.LeftButton:
            self.target_pos = event.pos()
            self.sequence_started = True
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.fade_out_anim = QPropertyAnimation(self, b"bg_opacity")
            self.fade_out_anim.setDuration(350)
            self.fade_out_anim.setStartValue(self._bg_opacity)
            self.fade_out_anim.setEndValue(0.0)
            self.fade_out_anim.finished.connect(self.start_phase1_walk)
            self.fade_out_anim.start()

    def start_phase1_walk(self) -> None:
        self.bgm_player.play()
        self.animator.load_animation("walk", target_height=430)
        start_x = -self.animator.width()
        start_y = max(0, self.target_pos.y() - self.animator.height() // 2 + 80)
        end_x = max(0, self.target_pos.x() - self.animator.width() + 100)

        self.animator.move(start_x, start_y)
        self.animator.show()
        self.animator.play(fps=7, loop=True)

        self.move_anim = QPropertyAnimation(self.animator, b"pos")
        self.move_anim.setDuration(3200)
        self.move_anim.setStartValue(QPoint(start_x, start_y))
        self.move_anim.setEndValue(QPoint(end_x, start_y))
        self.move_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.move_anim.finished.connect(self.start_phase2_point)
        self.move_anim.start()

    def start_phase2_point(self) -> None:
        self.sfx_player.play()
        self.animator.load_animation("point", target_height=430)
        try:
            self.animator.animationFinished.disconnect()
        except TypeError:
            pass
        self.animator.animationFinished.connect(self.show_dialog)
        self.animator.play(fps=6, loop=False)

    def show_dialog(self) -> None:
        try:
            self.animator.animationFinished.disconnect()
        except TypeError:
            pass

        if self.target_file:
            name = os.path.basename(self.target_file) or self.target_file
            mode_text = "永久删除（不可恢复）" if DELETE_MODE == "permanent" else "移入回收站"
            self.bubble.set_text(f"确认对“{name}”执行：{mode_text}？")
        else:
            self.bubble.set_text("当前是演示模式：只播放动画，不会删除任何文件。")

        global_pos = self.mapToGlobal(self.animator.pos())
        self.bubble.adjustSize()
        bubble_x = global_pos.x() + max(20, self.animator.width() // 2 - self.bubble.width() // 2)
        bubble_y = max(20, global_pos.y() - 20)
        self.bubble.move(bubble_x, bubble_y)
        self.bubble.show()

        self.choices.configure(bool(self.target_file))
        self.choices.adjustSize()
        choices_x = bubble_x + max(0, (self.bubble.width() - self.choices.width()) // 2)
        choices_y = bubble_y + self.bubble.height() + 8
        self.choices.move(choices_x, choices_y)
        try:
            self.choices.choiceMade.disconnect()
        except TypeError:
            pass
        self.choices.choiceMade.connect(self.on_choice)
        self.choices.show()

    def on_choice(self, confirmed: bool) -> None:
        self.choices.hide()
        if not confirmed:
            self.bubble.hide()
            self.on_app_exit()
            return
        self.bubble.hide()
        self.start_phase3_kick()

    def start_phase3_kick(self) -> None:
        try:
            self.animator.animationFinished.disconnect()
            self.animator.frameChanged.disconnect()
        except TypeError:
            pass
        self.animator.load_animation("kick", target_height=430)
        self.animator.frameChanged.connect(self.on_kick_frame)
        self.animator.animationFinished.connect(self.on_kick_finished)
        self.animator.play(fps=8, loop=False)

    def on_kick_frame(self, frame_idx: int) -> None:
        if frame_idx == 3:
            self.trigger_explosion()

    def trigger_explosion(self) -> None:
        self.exp_player.play()
        explosion_path = os.path.join(ASSET_DIR, "爆炸_spritesheet.png")
        if self.explosion_animator.load_spritesheet(explosion_path, target_height=170):
            exp_x = self.target_pos.x() - self.explosion_animator.width() // 2
            exp_y = self.target_pos.y() - self.explosion_animator.height() // 2 - 30
            self.explosion_animator.move(exp_x, exp_y)
            self.explosion_animator.show()
            try:
                self.explosion_animator.animationFinished.disconnect()
            except TypeError:
                pass
            self.explosion_animator.animationFinished.connect(self.explosion_animator.hide)
            self.explosion_animator.play(fps=8, loop=False)
        self.delete_target_file()

    def delete_target_file(self) -> None:
        if not self.target_file:
            self.delete_result = "演示模式：未删除文件。"
            return
        try:
            self.delete_result = delete_path(self.target_file)
            print(self.delete_result)
        except Exception as exc:
            self.delete_result = f"删除失败：{exc}"
            print(self.delete_result)

    def on_kick_finished(self) -> None:
        try:
            self.animator.animationFinished.disconnect()
            self.animator.frameChanged.disconnect()
        except TypeError:
            pass
        self.start_phase4_result()

    def start_phase4_result(self) -> None:
        self.animator.load_animation("idle", target_height=360)
        self.animator.play(fps=5, loop=True)
        if self.delete_result:
            self.bubble.set_text(self.delete_result)
            global_pos = self.mapToGlobal(self.animator.pos())
            self.bubble.adjustSize()
            self.bubble.move(global_pos.x() + 20, max(20, global_pos.y() - 30))
            self.bubble.show()
        QTimer.singleShot(1300, self.start_phase5_leave)

    def start_phase5_leave(self) -> None:
        self.bubble.hide()
        self.animator.load_animation("walk", target_height=430, mirror=True)
        self.animator.play(fps=7, loop=True)
        screen = QApplication.primaryScreen().geometry()
        self.move_anim2 = QPropertyAnimation(self.animator, b"pos")
        self.move_anim2.setDuration(1800)
        self.move_anim2.setStartValue(self.animator.pos())
        self.move_anim2.setEndValue(QPoint(screen.width() + 100, self.animator.pos().y()))
        self.move_anim2.setEasingCurve(QEasingCurve.Type.InQuad)
        self.move_anim2.finished.connect(self.on_app_exit)
        self.move_anim2.start()

    def on_app_exit(self) -> None:
        self.bgm_player.stop()
        self.sfx_player.stop()
        self.exp_player.stop()
        self.bubble.hide()
        self.choices.hide()
        self.close()
        QApplication.quit()


if __name__ == "__main__":
    register_context_menu()
    app = QApplication(sys.argv)
    target = sys.argv[1] if len(sys.argv) >= 2 else None
    window = MonsterDeleter(target)
    window.show()
    sys.exit(app.exec())
