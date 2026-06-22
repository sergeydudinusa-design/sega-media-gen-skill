"""Media-gen skill: MuAPI image and video generation.

Usage:
  python generate.py image --prompt "<text>" --title "<slug>"
                           [--model KEY] [--aspect-ratio 16:9]
                           [--input-image <path> ...]

  python generate.py video --image <path> --prompt "<text>" --title "<slug>"
                           --folder <existing folder> [--model KEY]
                           [--duration 5]

  python generate.py upscale --input <path> [--model KEY] [--title <slug>]

Returns a JSON line on stdout with paths.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
import urllib.request
from pathlib import Path

try:
    import requests
except ImportError:
    sys.stderr.write("ERROR: requests not installed. Run: pip install requests\n")
    sys.exit(2)

SKILL_ROOT = Path(__file__).resolve().parent.parent
BASE_URL = "https://api.muapi.ai/api/v1"
POLL_INTERVAL = 5
POLL_TIMEOUT = 600

ASPECT_TO_SIZE = {
    "1:1":  "1024*1024",
    "16:9": "1280*720",
    "9:16": "720*1280",
    "4:3":  "1024*768",
    "3:4":  "768*1024",
    "3:2":  "1152*768",
    "2:3":  "768*1152",
}


def load_config() -> tuple[dict, dict]:
    config = json.loads((SKILL_ROOT / "config.json").read_text(encoding="utf-8"))
    models = json.loads((SKILL_ROOT / "models.json").read_text(encoding="utf-8"))
    return config, models


def slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower())
    s = re.sub(r"[-\s]+", "-", s).strip("-")
    return s[:50] or "untitled"


def expand_path(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p)))


def get_or_make_folder(output_dir: Path, working_title: str) -> Path:
    date = time.strftime("%Y-%m-%d")
    folder = output_dir / f"{date}-{slugify(working_title)}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def next_index(folder: Path, kind: str, ext: str) -> int:
    pat = re.compile(rf"^{kind}-(\d+)\.{ext}$")
    used = [int(m.group(1)) for f in folder.iterdir() if (m := pat.match(f.name))]
    return (max(used) + 1) if used else 1


def download(url: str, dest: Path) -> None:
    urllib.request.urlretrieve(url, dest)


def require_key() -> str:
    key = os.environ.get("MUAPI_KEY")
    if not key:
        sys.stderr.write(
            "ERROR: MUAPI_KEY not set.\n"
            "  Mac/Linux: add `export MUAPI_KEY=\"<your-key>\"` to ~/.zshrc, then `source ~/.zshrc`\n"
            "  Windows: setx MUAPI_KEY \"<your-key>\"  (then restart terminal)\n"
        )
        sys.exit(3)
    return key


def upload_file(key: str, path: Path) -> str:
    """Upload local file to muapi CDN, return hosted URL."""
    sys.stderr.write(f"[media-gen] Uploading {path.name}...\n")
    sys.stderr.flush()
    with path.open("rb") as f:
        resp = requests.post(
            f"{BASE_URL}/upload_file",
            headers={"x-api-key": key},
            files={"file": (path.name, f)},
            timeout=120,
        )
    resp.raise_for_status()
    data = resp.json()
    url = (data.get("url")
           or data.get("data", {}).get("url")
           or (data.get("outputs") or [None])[0])
    if not url:
        sys.stderr.write(f"ERROR: upload response had no url: {json.dumps(data)[:500]}\n")
        sys.exit(6)
    return url


def submit(key: str, endpoint: str, payload: dict) -> str:
    """POST generation request, return request_id."""
    resp = requests.post(
        f"{BASE_URL}/{endpoint}",
        headers={"x-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    rid = (data.get("request_id")
           or data.get("id")
           or data.get("data", {}).get("id"))
    if not rid:
        sys.stderr.write(f"ERROR: submit response had no request_id: {json.dumps(data)[:500]}\n")
        sys.exit(7)
    return rid


def poll(key: str, request_id: str) -> list[str]:
    """Poll until completed, return outputs list."""
    deadline = time.time() + POLL_TIMEOUT
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        resp = requests.get(
            f"{BASE_URL}/predictions/{request_id}/result",
            headers={"x-api-key": key},
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json()
        body = raw.get("data") or raw
        status = body.get("status", "")
        if status == "completed":
            outputs = body.get("outputs", [])
            if not outputs:
                sys.stderr.write(f"ERROR: completed but no outputs: {json.dumps(raw)[:500]}\n")
                sys.exit(8)
            return outputs
        if status == "failed":
            sys.stderr.write(f"ERROR: generation failed: {body.get('error', 'unknown')}\n")
            sys.exit(9)
        sys.stderr.write(f"[media-gen] {status}...\n")
        sys.stderr.flush()
    sys.stderr.write("ERROR: timed out waiting for result\n")
    sys.exit(10)


def write_prompt_md(folder: Path, payload: dict) -> None:
    md = folder / "prompt.md"
    if not md.exists():
        md.write_text(
            f"# {payload.get('working_title', folder.name)}\n\n"
            f"**Created:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n",
            encoding="utf-8",
        )
    with md.open("a", encoding="utf-8") as f:
        kind = payload["kind"]
        f.write(f"\n## {kind.title()} generation\n\n")
        f.write(f"- **Endpoint:** `{payload['endpoint']}`\n")
        f.write(f"- **File:** `{payload['filename']}`\n")
        for k, v in payload.get("args", {}).items():
            f.write(f"- **{k}:** {v}\n")
        f.write(f"\n### {kind.title()} prompt\n\n{payload['prompt']}\n")


def cmd_image(args) -> None:
    key = require_key()
    config, models = load_config()
    output_dir = expand_path(config["output_dir"])

    img_cfg = models["image"]
    model_key = args.model or img_cfg["default"]
    if model_key not in img_cfg["models"]:
        sys.stderr.write(f"ERROR: unknown image model '{model_key}'. Available: {list(img_cfg['models'])}\n")
        sys.exit(4)
    spec = img_cfg["models"][model_key]
    if not spec.get("available", True):
        sys.stderr.write(f"ERROR: model '{model_key}' is not yet available on muapi.ai. Note: {spec.get('note','')}\n")
        sys.exit(11)

    payload = dict(spec.get("default_args", {}))
    payload["prompt"] = args.prompt
    if args.aspect_ratio:
        size = ASPECT_TO_SIZE.get(args.aspect_ratio)
        if size:
            payload["size"] = size

    if args.input_image:
        for raw in args.input_image:
            ip = expand_path(raw)
            if not ip.is_file():
                sys.stderr.write(f"ERROR: input image not found: {ip}\n")
                sys.exit(5)
        # muapi flux-dev takes a single `image` field for i2i
        payload["image"] = upload_file(key, expand_path(args.input_image[0]))

    folder = get_or_make_folder(output_dir, args.title)
    idx = next_index(folder, "image", "png")
    filename = f"image-{idx:02d}.png"
    out_path = folder / filename

    sys.stderr.write(f"[media-gen] Generating image with {spec['endpoint']}...\n")
    sys.stderr.flush()

    rid = submit(key, spec["endpoint"], payload)
    outputs = poll(key, rid)
    download(outputs[0], out_path)

    write_prompt_md(folder, {
        "kind": "image",
        "endpoint": spec["endpoint"],
        "filename": filename,
        "prompt": args.prompt,
        "working_title": args.title,
        "args": {k: v for k, v in payload.items() if k != "prompt"},
    })

    if args.input_image:
        for raw in args.input_image:
            ip = expand_path(raw)
            try:
                shutil.copy2(ip, folder / f"source-{ip.name}")
            except Exception:
                pass

    print(json.dumps({
        "image_path": str(out_path),
        "folder": str(folder),
        "model": spec["endpoint"],
        "url": outputs[0],
    }))


def cmd_video(args) -> None:
    key = require_key()
    config, models = load_config()

    vid_cfg = models["video"]
    model_key = args.model or vid_cfg["default"]
    if model_key not in vid_cfg["models"]:
        sys.stderr.write(f"ERROR: unknown video model '{model_key}'. Available: {list(vid_cfg['models'])}\n")
        sys.exit(4)
    spec = vid_cfg["models"][model_key]
    if not spec.get("available", True):
        sys.stderr.write(f"ERROR: model '{model_key}' is not yet available on muapi.ai. Note: {spec.get('note','')}\n")
        sys.exit(11)

    folder = expand_path(args.folder)
    if not folder.is_dir():
        sys.stderr.write(f"ERROR: folder does not exist: {folder}\n")
        sys.exit(5)

    payload = dict(spec.get("default_args", {}))
    payload["prompt"] = args.prompt

    if args.image:
        image_path = expand_path(args.image)
        if not image_path.is_file():
            sys.stderr.write(f"ERROR: image not found: {image_path}\n")
            sys.exit(5)
        payload["image_url"] = upload_file(key, image_path)
    if args.duration is not None:
        payload["duration"] = args.duration

    idx = next_index(folder, "video", "mp4")
    filename = f"video-{idx:02d}.mp4"
    out_path = folder / filename

    sys.stderr.write(f"[media-gen] Generating video with {spec['endpoint']} (1-3 min)...\n")
    sys.stderr.flush()

    rid = submit(key, spec["endpoint"], payload)
    outputs = poll(key, rid)
    download(outputs[0], out_path)

    write_prompt_md(folder, {
        "kind": "video",
        "endpoint": spec["endpoint"],
        "filename": filename,
        "prompt": args.prompt,
        "working_title": args.title,
        "args": {k: v for k, v in payload.items() if k not in ("prompt", "image_url")},
    })

    print(json.dumps({
        "video_path": str(out_path),
        "folder": str(folder),
        "model": spec["endpoint"],
        "url": outputs[0],
    }))


def cmd_upscale(args) -> None:
    key = require_key()
    config, models = load_config()
    output_dir = expand_path(config["output_dir"])

    in_path = expand_path(args.input)
    if not in_path.is_file():
        sys.stderr.write(f"ERROR: input file not found: {in_path}\n")
        sys.exit(5)

    cfg = models["upscale"]
    model_key = args.model or cfg["default"]
    if model_key not in cfg["models"]:
        sys.stderr.write(f"ERROR: unknown upscale model '{model_key}'. Available: {list(cfg['models'])}\n")
        sys.exit(4)
    spec = cfg["models"][model_key]
    if not spec.get("available", True):
        sys.stderr.write(f"ERROR: model '{model_key}' is not yet available on muapi.ai. Note: {spec.get('note','')}\n")
        sys.exit(11)

    work_title = args.title or slugify(in_path.stem)
    folder = get_or_make_folder(output_dir, work_title)

    sys.stderr.write(f"[media-gen] Upscaling {in_path.name} via {spec['endpoint']}...\n")
    sys.stderr.flush()

    src_url = upload_file(key, in_path)
    payload = dict(spec.get("default_args", {}))
    payload["image_url"] = src_url

    rid = submit(key, spec["endpoint"], payload)
    outputs = poll(key, rid)

    ext = in_path.suffix.lstrip(".") or "png"
    idx = next_index(folder, "upscaled", ext)
    filename = f"upscaled-{idx:02d}.{ext}"
    out_path = folder / filename
    download(outputs[0], out_path)

    write_prompt_md(folder, {
        "kind": "upscale",
        "endpoint": spec["endpoint"],
        "filename": filename,
        "prompt": f"Upscale of {in_path.name}",
        "working_title": work_title,
        "args": {k: v for k, v in payload.items() if k != "image_url"},
    })

    print(json.dumps({
        "upscaled_path": str(out_path),
        "folder": str(folder),
        "model": spec["endpoint"],
        "url": outputs[0],
    }))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="media-gen")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("image", help="Generate an image from a prompt")
    pi.add_argument("--prompt", required=True)
    pi.add_argument("--title", required=True)
    pi.add_argument("--model", default=None)
    pi.add_argument("--aspect-ratio", dest="aspect_ratio", default=None)
    pi.add_argument("--input-image", dest="input_image", action="append", default=None,
                    help="Reference image for image-to-image. Repeat for multiple.")
    pi.set_defaults(func=cmd_image)

    pv = sub.add_parser("video", help="Generate video (omit --image for text-to-video)")
    pv.add_argument("--image", default=None, help="Source image for I2V. Omit for T2V.")
    pv.add_argument("--prompt", required=True)
    pv.add_argument("--title", required=True)
    pv.add_argument("--folder", required=True)
    pv.add_argument("--model", default=None)
    pv.add_argument("--duration", type=int, default=None)
    pv.set_defaults(func=cmd_video)

    pu = sub.add_parser("upscale", help="Upscale an image to higher resolution")
    pu.add_argument("--input", required=True)
    pu.add_argument("--model", default=None)
    pu.add_argument("--title", default=None)
    pu.set_defaults(func=cmd_upscale)

    return p


if __name__ == "__main__":
    args = build_parser().parse_args()
    args.func(args)
