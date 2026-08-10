import os
import re
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QPainter, QPixmap, QTransform
from PyQt6.QtWidgets import QLabel


def get_resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


ASSET_DIR = Path(get_resource_path("assets"))
CHARACTER_DIR = ASSET_DIR / "character" / "generated"
REQUIRED_POSES = ("walk", "point", "kick")


def _natural_key(path: Path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]


def pose_files(action: str) -> list[Path]:
    candidates: list[Path] = []
    single = CHARACTER_DIR / f"{action}.png"
    if single.exists():
        candidates.append(single)
    folder = CHARACTER_DIR / action
    if folder.exists():
        for ext in ("*.png", "*.webp", "*.jpg", "*.jpeg"):
            candidates.extend(folder.glob(ext))
    return sorted({p.resolve() for p in candidates}, key=_natural_key)


def missing_pose_assets() -> list[str]:
    return [action for action in REQUIRED_POSES if not pose_files(action)]


class PoseAnimator(QLabel):
    """Animate distinct AI-generated action images with subtle secondary motion."""

    animationFinished = pyqtSignal()
    frameChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.frames: list[QPixmap] = []
        self.current_frame = 0
        self.loop = True
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)

    def _load_sources(self, action: str, target_height: int, mirror: bool) -> list[QPixmap]:
        result: list[QPixmap] = []
        for path in pose_files(action):
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            pixmap = pixmap.scaledToHeight(target_height, Qt.TransformationMode.SmoothTransformation)
            if mirror:
                pixmap = pixmap.transformed(QTransform().scale(-1, 1), Qt.TransformationMode.SmoothTransformation)
            result.append(pixmap)
        return result

    @staticmethod
    def _motion_pattern(action: str):
        # The pose itself is AI-generated. These transforms only add breathing/bob/impact motion.
        if action == "walk":
            return [(-1.2, 1.000, 5), (0.0, 1.012, 0), (1.2, 1.000, 5), (0.0, 1.008, 1)]
        if action == "point":
            return [(-0.4, 1.000, 1), (0.0, 1.010, -1), (0.4, 1.000, 0)]
        if action == "kick":
            return [(0.0, 0.970, 2), (-1.0, 1.000, 0), (1.2, 1.065, -4), (0.0, 1.020, 0)]
        return [(0.0, 1.000, 0)]

    @staticmethod
    def _compose(source: QPixmap, angle: float, scale: float, yoff: int, canvas_w: int, canvas_h: int) -> QPixmap:
        transformed = source.transformed(QTransform().rotate(angle).scale(scale, scale), Qt.TransformationMode.SmoothTransformation)
        canvas = QPixmap(canvas_w, canvas_h)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = (canvas_w - transformed.width()) // 2
        y = canvas_h - transformed.height() - 20 + yoff
        painter.drawPixmap(x, y, transformed)
        painter.end()
        return canvas

    def load_action(self, action: str, target_height: int = 470, mirror: bool = False) -> bool:
        sources = self._load_sources(action, target_height, mirror)
        if not sources:
            self.frames = []
            return False

        max_w = max(p.width() for p in sources)
        max_h = max(p.height() for p in sources)
        canvas_w, canvas_h = max_w + 180, max_h + 180
        pattern = self._motion_pattern(action)

        self.frames = []
        for index, source in enumerate(sources):
            for angle, scale, yoff in pattern:
                signed_angle = angle if index % 2 == 0 else -angle
                self.frames.append(self._compose(source, signed_angle, scale, yoff, canvas_w, canvas_h))

        self.current_frame = 0
        self.resize(canvas_w, canvas_h)
        self._update_frame()
        return True

    def play(self, fps: int = 8, loop: bool = True) -> None:
        if not self.frames:
            return
        self.loop = loop
        self.current_frame = 0
        self.timer.start(max(1, 1000 // fps))
        self._update_frame()

    def stop(self) -> None:
        self.timer.stop()

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

    def load_spritesheet(self, filepath: str, cols: int = 5, rows: int = 3, target_height: int = 180) -> bool:
        transparent = filepath.replace(".png", "_transparent.png")
        if os.path.exists(transparent):
            filepath = transparent
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
        if not self.frames:
            return False
        self.resize(self.frames[0].size())
        self.setPixmap(self.frames[0])
        return True

    def play(self, fps: int = 9, loop: bool = False) -> None:
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
