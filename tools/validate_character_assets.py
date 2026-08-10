from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CHARACTER_DIR = ROOT / "assets" / "character" / "generated"
ACTIONS = ("walk", "point", "kick")


def files_for(action: str) -> list[Path]:
    direct = CHARACTER_DIR / f"{action}.png"
    result = [direct] if direct.exists() else []
    folder = CHARACTER_DIR / action
    if folder.exists():
        result.extend(sorted(folder.glob("*.png")))
    return result


def main() -> int:
    errors: list[str] = []
    for action in ACTIONS:
        files = files_for(action)
        if not files:
            errors.append(f"{action}: no PNG pose asset found")
            continue
        for path in files:
            try:
                with Image.open(path) as image:
                    if image.width < 200 or image.height < 300:
                        errors.append(f"{path}: image is too small ({image.width}x{image.height})")
                    if image.mode not in ("RGBA", "LA") and "transparency" not in image.info:
                        errors.append(f"{path}: image has no alpha channel; use transparent PNG")
                    else:
                        lo, _ = image.convert("RGBA").getchannel("A").getextrema()
                        if lo >= 250:
                            errors.append(f"{path}: alpha channel is effectively opaque; remove the background")
            except Exception as exc:
                errors.append(f"{path}: cannot open image ({exc})")

    if errors:
        print("[ERROR] AI character assets are not ready:")
        for error in errors:
            print(f"  - {error}")
        print("\nGenerate them first with:")
        print("  python tools\\comfyui_generate_poses.py")
        return 2

    print("[OK] AI character assets validated:")
    for action in ACTIONS:
        print(f"  {action}: {len(files_for(action))} file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
