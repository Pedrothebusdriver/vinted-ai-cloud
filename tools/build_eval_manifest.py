"""Build a sampler manifest from local training data.

Reads `data/training_items.jsonl` and writes `.agent/sampler/manifest-*.json`
that points at Pete's own images instead of Openverse.
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATASET = ROOT / "data" / "training_items.jsonl"
DEFAULT_OUT_DIR = ROOT / ".agent" / "sampler"


def load_items(path: Path) -> Iterable[Dict]:
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        yield obj


def build_manifest(items: List[Dict], dataset_path: Path) -> Dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "ts": ts,
        "source": "local-training-set",
        "dataset": str(dataset_path),
        "items": [],
    }
    for idx, obj in enumerate(items, start=1):
        image_path = Path(obj["image_path"])
        manifest["items"].append(
            {
                "id": idx,
                "image_path": str(image_path),
                "labels": {
                    "brand": obj.get("brand"),
                    "size": obj.get("size"),
                    "colour": obj.get("colour"),
                    "category": obj.get("category"),
                    "condition": obj.get("condition"),
                    "price_low": obj.get("price_low"),
                    "price_mid": obj.get("price_mid"),
                    "price_high": obj.get("price_high"),
                },
            }
        )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build sampler manifest from local training data")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Path to training_items.jsonl")
    parser.add_argument("--out", type=Path, default=None, help="Optional output manifest path")
    args = parser.parse_args()

    dataset_path = args.dataset if args.dataset.is_absolute() else (ROOT / args.dataset)
    if not dataset_path.exists():
        raise SystemExit(f"Dataset not found: {dataset_path}")

    items = list(load_items(dataset_path))
    if not items:
        raise SystemExit(f"No rows in dataset: {dataset_path}")

    manifest = build_manifest(items, dataset_path)

    out_path = args.out
    if out_path is None:
        out_path = DEFAULT_OUT_DIR / f"manifest-{manifest['ts']}.json"
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Wrote {out_path} ({len(manifest['items'])} items)")


if __name__ == "__main__":
    main()
