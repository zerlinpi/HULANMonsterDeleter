import base64
import io
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw
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
EMBEDDED_DIR = ASSET_DIR / "character" / "embedded"
REQUIRED_POSES = ("walk", "point", "kick")
EMBEDDED_FRAMES = {
    "walk": ("walk_01", "walk_02", "walk_03", "walk_04"),
    "point": ("point_01", "point_02", "point_03"),
    "kick": ("kick_01", "kick_02", "kick_03"),
}


def _natural_key(path: Path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]


def pose_files(action: str) -> list[Path]:
    """Return optional local image overrides for an action.

    Files placed under assets/character/generated/<action>/ take precedence over
    the embedded frames shipped in the repository. This keeps the app easy to
    reskin later without changing Python code.
    """
    candidates: list[Path] = []
    single = CHARACTER_DIR / f"{action}.png"
    if single.exists():
        candidates.append(single)
    folder = CHARACTER_DIR / action
    if folder.exists():
        for ext in ("*.png", "*.webp", "*.jpg", "*.jpeg"):
            candidates.extend(folder.glob(ext))
    return sorted({p.resolve() for p in candidates}, key=_natural_key)


def embedded_frame_paths(action: str) -> list[Path]:
    return [EMBEDDED_DIR / f"{name}.b64" for name in EMBEDDED_FRAMES.get(action, ())]


def embedded_action_ready(action: str) -> bool:
    paths = embedded_frame_paths(action)
    return bool(paths) and all(path.exists() and path.stat().st_size > 100 for path in paths)


def missing_pose_assets() -> list[str]:
    return [
        action
        for action in REQUIRED_POSES
        if not pose_files(action) and not embedded_action_ready(action)
    ]


def _strip_connected_white_background(image: Image.Image) -> Image.Image:
    """Turn the generated white studio background into alpha.

    Flood fill starts only from the canvas edges, so white clothing and shoes
    inside the character remain opaque instead of being globally color-keyed.
    """
    image = image.convert("RGBA")
    draw_image = image.copy()
    width, height = draw_image.size

    seeds: set[tuple[int, int]] = {
        (0, 0),
        (max(0, width - 1), 0),
        (0, max(0, height - 1)),
        (max(0, width - 1), max(0, height - 1)),
    }
    step_x = max(1, width // 8)
    step_y = max(1, height // 8)
    for x in range(0, width, step_x):
        seeds.add((x, 0))
        seeds.add((x, height - 1))
    for y in range(0, height, step_y):
        seeds.add((0, y))
        seeds.add((width - 1, y))

    for seed in seeds:
        r, g, b, a = draw_image.getpixel(seed)
        if a > 0 and min(r, g, b) >= 185 and max(r, g, b) - min(r, g, b) <= 55:
            ImageDraw.floodfill(draw_image, seed, (255, 255, 255, 0), thresh=55)

    alpha = draw_image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox:
        left, top, right, bottom = bbox
        pad = 4
        bbox = (
            max(0, left - pad),
            max(0, top - pad),
            min(width, right + pad),
            min(height, bottom + pad),
        )
        draw_image = draw_image.crop(bbox)
    return draw_image


def _pil_to_pixmap(image: Image.Image) -> QPixmap:
    rgba = image.convert("RGBA")
    raw = rgba.tobytes("raw", "RGBA")
    qimage = QImage(raw, rgba.width, rgba.height, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


def _load_embedded_pixmap(path: Path) -> QPixmap:
    try:
        payload = path.read_text(encoding="utf-8").strip()
        data = base64.b64decode(payload, validate=True)
        with Image.open(io.BytesIO(data)) as source:
            cutout = _strip_connected_white_background(source)
        return _pil_to_pixmap(cutout)
    except Exception as exc:
        print(f"Failed to decode embedded action frame {path}: {exc}")
        return QPixmap()


class PoseAnimator(QLabel):
    """Play actual AI-generated action frames without fake pose transforms."""

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
        overrides = pose_files(action)
        if overrides:
            for path in overrides:
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    result.append(pixmap)
        else:
            for path in embedded_frame_paths(action):
                pixmap = _load_embedded_pixmap(path)
                if not pixmap.isNull():
                    result.append(pixmap)

        normalized: list[QPixmap] = []
        for pixmap in result:
            pixmap = pixmap.scaledToHeight(target_height, Qt.TransformationMode.SmoothTransformation)
            if mirror:
                pixmap = pixmap.transformed(
                    QTransform().scale(-1, 1),
                    Qt.TransformationMode.SmoothTransformation,
                )
            normalized.append(pixmap)
        return normalized

    @staticmethod
    def _place_on_canvas(source: QPixmap, canvas_w: int, canvas_h: int) -> QPixmap:
        canvas = QPixmap(canvas_w, canvas_h)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        x = (canvas_w - source.width()) // 2
        y = canvas_h - source.height() - 24
        painter.drawPixmap(x, y, source)
        painter.end()
        return canvas

    def load_action(self, action: str, target_height: int = 470, mirror: bool = False) -> bool:
        sources = self._load_sources(action, target_height, mirror)
        if not sources:
            self.frames = []
            return False

        max_w = max(p.width() for p in sources)
        max_h = max(p.height() for p in sources)
        canvas_w = max_w + 80
        canvas_h = max_h + 64

        # One source image equals one animation frame. No rotation, scaling pulse,
        # or synthetic body warp is inserted here.
        self.frames = [self._place_on_canvas(source, canvas_w, canvas_h) for source in sources]
        self.current_frame = 0
        self.resize(canvas_w, canvas_h)
        self._update_frame()
        return True

    def play(self, fps: int = 6, loop: bool = True) -> None:
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
