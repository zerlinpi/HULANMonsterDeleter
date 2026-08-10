import base64
import io
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHARACTER_DIR = ROOT / "assets" / "character" / "generated"
EMBEDDED_DIR = ROOT / "assets" / "character" / "embedded"
EMBEDDED_FRAMES = {
    "walk": ("walk_01", "walk_02", "walk_03", "walk_04"),
    "point": ("point_01", "point_02", "point_03"),
    "kick": ("kick_01", "kick_02", "kick_03"),
}


def override_files(action: str) -> list[Path]:
    direct = CHARACTER_DIR / f"{action}.png"
    result = [direct] if direct.exists() else []
    folder = CHARACTER_DIR / action
    if folder.exists():
        for ext in ("*.png", "*.webp", "*.jpg", "*.jpeg"):
            result.extend(sorted(folder.glob(ext)))
    return result


def embedded_files(action: str) -> list[Path]:
    return [EMBEDDED_DIR / f"{name}.b64" for name in EMBEDDED_FRAMES[action]]


def validate_image(image: Image.Image, label: str, errors: list[str]) -> None:
    if image.width < 200 or image.height < 300:
        errors.append(f"{label}: image is too small ({image.width}x{image.height})")


def validate_override(path: Path, errors: list[str]) -> None:
    try:
        with Image.open(path) as image:
            validate_image(image, str(path), errors)
    except Exception as exc:
        errors.append(f"{path}: cannot open image ({exc})")


def validate_embedded(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"{path}: embedded frame is missing")
        return
    try:
        payload = path.read_text(encoding="utf-8").strip()
        data = base64.b64decode(payload, validate=True)
        with Image.open(io.BytesIO(data)) as image:
            validate_image(image, str(path), errors)
    except Exception as exc:
        errors.append(f"{path}: invalid embedded image ({exc})")


def main() -> int:
    errors: list[str] = []
    counts: dict[str, int] = {}

    for action in EMBEDDED_FRAMES:
        overrides = override_files(action)
        if overrides:
            counts[action] = len(overrides)
            for path in overrides:
                validate_override(path, errors)
            continue

        frames = embedded_files(action)
        counts[action] = len(frames)
        for path in frames:
            validate_embedded(path, errors)

    if errors:
        print("[ERROR] AI character assets are not ready:")
        for error in errors:
            print(f"  - {error}")
        print("\nThe repository should already contain these frames. Run git pull again if files are missing.")
        return 2

    print("[OK] Included AI character assets validated:")
    for action in ("walk", "point", "kick"):
        print(f"  {action}: {counts[action]} frame(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
