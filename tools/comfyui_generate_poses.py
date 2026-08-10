"""Generate walk / point / kick key poses through a local ComfyUI API.

The workflow uses built-in ComfyUI nodes only: checkpoint loader, img2img,
KSampler, VAE decode and SaveImage. The generated subject is requested on a
chroma-green background; Pillow/Numpy remove that background into transparent
PNG files consumed by the desktop application.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from embedded_photos import PHOTO_FULL_B64  # noqa: E402

POSITIVE_BASE = (
    "same person as the reference photo, preserve the same face identity, same black hairstyle, "
    "same peach pink off-shoulder blouse with flower decorations, same white pleated skirt, "
    "same white socks and white platform sneakers, realistic photography, full body visible from head to shoes, "
    "correct anatomy, natural proportions, isolated studio character cutout, pure chroma green #00ff00 background, "
    "even lighting, centered subject, no crop"
)
NEGATIVE = (
    "different person, changed identity, different face, different clothes, extra person, duplicate body, extra arms, "
    "extra legs, extra fingers, missing fingers, malformed hands, malformed feet, deformed anatomy, cropped head, cropped shoes, "
    "text, logo, watermark, background objects, scenery, furniture, heavy shadow, green clothes, low resolution, blurry face"
)
ACTION_PROMPTS = {
    "walk": [
        "walking briskly toward the right, natural mid-stride, left foot forward, right foot back, arms naturally counter-swinging, looking toward the right",
        "walking briskly toward the right, next gait phase, right foot forward, left foot back, arms naturally counter-swinging, looking toward the right",
    ],
    "point": [
        "standing three-quarter view facing right, starting to extend the right arm toward the right, index finger clearly pointing at an object to the right",
        "standing three-quarter view facing right, right arm fully extended, index finger clearly pointing horizontally to the right, confident readable pointing gesture",
    ],
    "kick": [
        "dynamic side-kick preparation facing right, supporting leg planted, kicking knee raised toward the right, upper body balanced, action pose",
        "dynamic full side kick toward the right, one leg fully extended toward the right at about waist height, supporting leg planted, upper body slightly leaned back, strong readable impact pose",
    ],
}


def http_json(url: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    data = None
    headers = {}
    method = "GET"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
        method = "POST"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def discover_checkpoints(server: str) -> list[str]:
    info = http_json(server.rstrip("/") + "/object_info/CheckpointLoaderSimple")
    node = info.get("CheckpointLoaderSimple", info)
    try:
        return [str(x) for x in node["input"]["required"]["ckpt_name"][0]]
    except Exception:
        return []


def export_reference(output: Path) -> None:
    image = Image.open(io.BytesIO(base64.b64decode(PHOTO_FULL_B64))).convert("RGB")
    if image.height > 1024:
        scale = 1024 / image.height
        image = image.resize((max(1, int(image.width * scale)), 1024), Image.Resampling.LANCZOS)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=94)


def upload_image(server: str, image_path: Path) -> str:
    boundary = "----MonsterDeleter" + uuid.uuid4().hex
    pieces: list[bytes] = []

    def field(name: str, value: str) -> None:
        pieces.extend([
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
            value.encode(),
            b"\r\n",
        ])

    field("overwrite", "true")
    field("type", "input")
    pieces.extend([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="image"; filename="{image_path.name}"\r\n'.encode(),
        b"Content-Type: image/jpeg\r\n\r\n",
        image_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        server.rstrip("/") + "/upload/image",
        data=b"".join(pieces),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    name = result.get("name") or image_path.name
    subfolder = result.get("subfolder") or ""
    return f"{subfolder}/{name}" if subfolder else name


def workflow(checkpoint: str, uploaded_image: str, prompt: str, seed: int, prefix: str, denoise: float) -> dict:
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {"class_type": "LoadImage", "inputs": {"image": uploaded_image}},
        "3": {"class_type": "VAEEncode", "inputs": {"pixels": ["2", 0], "vae": ["1", 2]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": NEGATIVE, "clip": ["1", 1]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": 30,
                "cfg": 5.5,
                "sampler_name": "dpmpp_2m",
                "scheduler": "karras",
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["3", 0],
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["7", 0]}},
    }


def queue_prompt(server: str, graph: dict) -> str:
    result = http_json(server.rstrip("/") + "/prompt", {"prompt": graph, "client_id": uuid.uuid4().hex}, timeout=60)
    prompt_id = result.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI did not return prompt_id: {result}")
    return str(prompt_id)


def wait_for_output(server: str, prompt_id: str, timeout: float = 600.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        history = http_json(server.rstrip("/") + f"/history/{prompt_id}", timeout=30)
        record = history.get(prompt_id)
        if record:
            status = record.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI generation failed: {status}")
            for node_output in record.get("outputs", {}).values():
                images = node_output.get("images") or []
                if images:
                    return images[-1]
        time.sleep(1.0)
    raise TimeoutError(f"Timed out waiting for ComfyUI prompt {prompt_id}")


def download_output(server: str, image_meta: dict) -> bytes:
    params = urllib.parse.urlencode({
        "filename": image_meta["filename"],
        "subfolder": image_meta.get("subfolder", ""),
        "type": image_meta.get("type", "output"),
    })
    with urllib.request.urlopen(server.rstrip("/") + "/view?" + params, timeout=60) as resp:
        return resp.read()


def remove_chroma_green(image_bytes: bytes, output: Path) -> None:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    arr = np.array(image).astype(np.int16)
    rgb = arr[..., :3]
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    greenness = g - np.maximum(r, b)
    alpha = np.full(g.shape, 255, dtype=np.int16)
    keyed = (g > 90) & (greenness > 18)
    alpha[keyed] = np.clip(255 - (greenness[keyed] - 18) * 5, 0, 255)
    spill = keyed & (alpha > 0)
    rgb[..., 1][spill] = np.minimum(rgb[..., 1][spill], np.maximum(r[spill], b[spill]) + 24)
    arr[..., :3] = np.clip(rgb, 0, 255)
    arr[..., 3] = alpha
    result = Image.fromarray(arr.astype(np.uint8), "RGBA")
    bbox = result.getbbox()
    if bbox:
        result = result.crop(bbox)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate walk / point / kick AI poses through local ComfyUI.")
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--checkpoint", default="", help="Exact ComfyUI checkpoint filename")
    parser.add_argument("--denoise", type=float, default=0.74, help="Typical range: 0.68-0.80")
    parser.add_argument("--variants", type=int, default=2, choices=(1, 2))
    parser.add_argument("--seed", type=int, default=260810)
    args = parser.parse_args()

    server = args.server.rstrip("/")
    try:
        checkpoints = discover_checkpoints(server)
    except (urllib.error.URLError, ConnectionError) as exc:
        print(f"[ERROR] Cannot connect to ComfyUI at {server}: {exc}")
        print("Start ComfyUI first, e.g. python main.py --listen 127.0.0.1 --port 8188")
        return 2

    checkpoint = args.checkpoint.strip()
    if not checkpoint:
        if len(checkpoints) == 1:
            checkpoint = checkpoints[0]
        else:
            print("[ERROR] Choose a checkpoint with --checkpoint. Available checkpoints:")
            for name in checkpoints:
                print(f"  - {name}")
            return 2
    elif checkpoints and checkpoint not in checkpoints:
        print(f"[ERROR] Checkpoint not found: {checkpoint}")
        for name in checkpoints:
            print(f"  - {name}")
        return 2

    ref_path = ROOT / ".pose_generation" / "reference_full.jpg"
    export_reference(ref_path)
    uploaded = upload_image(server, ref_path)
    output_root = ROOT / "assets" / "character" / "generated"
    output_root.mkdir(parents=True, exist_ok=True)
    offsets = {"walk": 0, "point": 1000, "kick": 2000}

    for action in ("walk", "point", "kick"):
        action_dir = output_root / action
        action_dir.mkdir(parents=True, exist_ok=True)
        for old in action_dir.glob("frame_*.png"):
            old.unlink()
        prompts = ACTION_PROMPTS[action][: args.variants]
        action_seed = args.seed + offsets[action]
        for index, action_prompt in enumerate(prompts, start=1):
            positive = POSITIVE_BASE + ", " + action_prompt
            graph = workflow(checkpoint, uploaded, positive, action_seed, f"MonsterDeleter/{action}_{index:02d}", args.denoise)
            print(f"[{action}] generating {index}/{len(prompts)} ...")
            meta = wait_for_output(server, queue_prompt(server, graph))
            output = action_dir / f"frame_{index:03d}.png"
            remove_chroma_green(download_output(server, meta), output)
            print(f"  saved: {output.relative_to(ROOT)}")

    print("\nAI action assets generated successfully.")
    print("Next: python main.py")
    print("Then: build.bat")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
