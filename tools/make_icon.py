from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from embedded_photos import PHOTO_CLOSE_B64


def main() -> None:
    image = Image.open(BytesIO(base64.b64decode(PHOTO_CLOSE_B64))).convert("RGB")
    w, h = image.size

    # Face-focused crop from the second supplied photo.
    crop = image.crop((int(w * 0.26), int(h * 0.04), int(w * 0.78), int(h * 0.40)))
    icon = ImageOps.fit(crop, (512, 512), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5)).convert("RGBA")

    mask = Image.new("L", (512, 512), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((8, 8, 504, 504), radius=112, fill=255)
    icon.putalpha(mask)

    out_dir = ROOT / "assets" / "generated"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "photo_character.ico"
    icon.save(out_path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"Generated: {out_path}")


if __name__ == "__main__":
    main()
