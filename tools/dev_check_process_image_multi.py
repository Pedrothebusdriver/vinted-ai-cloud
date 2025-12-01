#!/usr/bin/env python3
"""
Quick sanity check for multi-photo /process_image.

Usage:
    python tools/dev_check_process_image_multi.py [base_url]
Default base_url: http://localhost:5055
"""

import base64
import json
import os
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path

import requests

SAMPLE_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJ"
    "RU5ErkJggg=="
)


def write_sample_images(tmpdir: Path, count: int = 3):
    data = base64.b64decode(SAMPLE_PNG)
    paths = []
    for idx in range(count):
        path = tmpdir / f"sample_{idx + 1}.png"
        path.write_bytes(data)
        paths.append(path)
    return paths


def run(base_url: str):
    base = base_url.rstrip("/")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        paths = write_sample_images(tmpdir)
        with ExitStack() as stack:
            handles = [stack.enter_context(open(p, "rb")) for p in paths]
            files = [
                ("file", ("sample_1.png", handles[0], "image/png")),
                ("files", ("sample_2.png", handles[1], "image/png")),
                ("files", ("sample_3.png", handles[2], "image/png")),
            ]
            payload = {
                "metadata": json.dumps({"brand": "TestBrand", "size": "M"}),
            }
            url = f"{base}/process_image"
            print(f"POST {url} with {len(files)} files...")
            res = requests.post(url, files=files, data=payload, timeout=15)
    res.raise_for_status()
    data = res.json()
    photos = data.get("photos") or []
    print(f"Status: {res.status_code}, draft_id: {data.get('id')}, photos: {len(photos)}")
    assert len(photos) == 3, f"Expected 3 photos, got {len(photos)}"
    print("OK: /process_image returned all photos.")


if __name__ == "__main__":
    base_arg = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("FLIPLENS_BASE")
    base = base_arg or "http://localhost:5055"
    try:
        run(base)
    except Exception as exc:  # pragma: no cover - simple smoke script
        print(f"Check failed: {exc}")
        sys.exit(1)
