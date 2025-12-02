"""
Tiny helper to simulate a bulk upload against the local app.py server.

Usage:
    source .venv/bin/activate
    python tools/simulate_bulk_upload.py --count 10 --group-size 4 --base-url http://localhost:5000
"""

import argparse
import io
import json
import random
from typing import List

import requests


def _make_dummy_file(idx: int) -> tuple:
    payload = f"fake-image-{idx}".encode("utf-8")
    fileobj = io.BytesIO(payload)
    fileobj.name = f"photo-{idx}.jpg"
    return ("file", (fileobj.name, fileobj, "image/jpeg"))


def chunk(items: List[int], size: int) -> List[List[int]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def simulate(base_url: str, total: int, group_size: int) -> None:
    batches = chunk(list(range(1, total + 1)), group_size)
    print(f"Simulating {len(batches)} drafts from {total} photos ({group_size} per draft)...")
    created_ids: List[str] = []
    for batch in batches:
        files = [_make_dummy_file(i) for i in batch]
        metadata = {
            "brand": random.choice(["Nike", "Adidas", "Zara", "Barbour"]),
            "size": random.choice(["S", "M", "L", "UK 10"]),
            "condition": random.choice(["Good", "Excellent"]),
        }
        resp = requests.post(
            f"{base_url}/process_image",
            files=files,
            data={"metadata": json.dumps(metadata)},
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        created_ids.append(str(payload.get("id")))
        print(
            f"- Draft {payload.get('id')}: {payload.get('title')} "
            f"£{payload.get('price_low')}-{payload.get('price_high')} "
            f"brand={payload.get('brand')} size={payload.get('size')} condition={payload.get('condition')}"
        )
    print(f"Created {len(created_ids)} drafts: {', '.join(created_ids)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate a bulk upload.")
    parser.add_argument("--base-url", default="http://localhost:5000", help="app.py server base URL")
    parser.add_argument("--count", type=int, default=8, help="How many fake photos to send.")
    parser.add_argument(
        "--group-size",
        type=int,
        default=4,
        help="How many photos per draft to simulate (client grouping analogue).",
    )
    args = parser.parse_args()
    simulate(args.base_url, args.count, args.group_size)


if __name__ == "__main__":
    main()
