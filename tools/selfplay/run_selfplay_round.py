"""
Generate self-play prediction/correction logs from scraped listings.

Outputs JSONL to:
- tools/marketplace_eval/data/selfplay_predictions.jsonl
- tools/marketplace_eval/data/selfplay_corrections.jsonl
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List
CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from inference_core import infer_listing, load_heuristics_config

SELFPLAY_DIR = CURRENT_FILE.parent
SCRAPED_LISTINGS_PATH = SELFPLAY_DIR / "data" / "scraped_listings.jsonl"
MARKETPLACE_DATA_DIR = CURRENT_FILE.parents[1] / "marketplace_eval" / "data"

# Reuse the placeholder listings from the scraper when no data is available.
try:
    from tools.selfplay.scrape_vinted_listings import PLACEHOLDER_LISTINGS  # type: ignore
except Exception:  # noqa: BLE001
    PLACEHOLDER_LISTINGS = []


def _timestamp() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _write_jsonl(records: Iterable[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _normalise_listing(raw: Dict[str, Any], idx: int) -> Dict[str, Any]:
    return {
        "id": str(raw.get("id") or f"listing-{idx}"),
        "title": raw.get("title") or "",
        "description": raw.get("description") or "",
        "brand": raw.get("brand"),
        "size": raw.get("size"),
        "colour": raw.get("colour"),
        "condition": raw.get("condition"),
        "category": raw.get("category"),
        "price_gbp": raw.get("price_gbp"),
        "currency": "GBP",
    }


def _placeholder_listings(max_examples: int) -> List[Dict[str, Any]]:
    if PLACEHOLDER_LISTINGS:
        items: List[Dict[str, Any]] = []
        for idx in range(max_examples):
            template = PLACEHOLDER_LISTINGS[idx % len(PLACEHOLDER_LISTINGS)].copy()
            template["id"] = f"{template.get('id', 'placeholder')}-{idx}"
            template["scraped_at"] = _timestamp()
            items.append(template)
        return items

    return [
        {
            "id": f"fallback-{idx}",
            "title": "Self-play placeholder item",
            "description": "Auto-generated placeholder listing.",
            "brand": None,
            "size": None,
            "colour": None,
            "condition": None,
            "category": None,
            "price_gbp": 20.0 + idx,
            "currency": "GBP",
            "scraped_at": _timestamp(),
        }
        for idx in range(max_examples)
    ]


def _load_scraped_listings(path: Path, max_examples: int) -> List[Dict[str, Any]]:
    if not path.exists():
        print(f"No scraped listings found at {path}; falling back to placeholders.")
        return _placeholder_listings(max_examples)

    listings: List[Dict[str, Any]] = []
    try:
        if path.suffix == ".jsonl":
            listings = _read_jsonl(path)
        else:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, list):
                    listings = data
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to read scraped listings ({exc}); using placeholders instead.")
        return _placeholder_listings(max_examples)

    if not listings:
        print("Scraped listing file was empty; using placeholders instead.")
        return _placeholder_listings(max_examples)

    normalised = [_normalise_listing(item, idx) for idx, item in enumerate(listings, start=1)]
    return normalised[:max_examples]


def _build_truth(listing: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": listing.get("title") or "",
        "description": listing.get("description") or "",
        "brand": listing.get("brand"),
        "size": listing.get("size"),
        "colour": listing.get("colour"),
        "condition": listing.get("condition"),
        "category": listing.get("category"),
        "price_gbp": listing.get("price_gbp"),
        "currency": "GBP",
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a self-play round over scraped listings.")
    parser.add_argument(
        "--max-examples",
        type=int,
        default=100,
        help="Maximum examples from the scraped listing set.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=SCRAPED_LISTINGS_PATH,
        help="Path to scraped listings (JSONL or JSON).",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=MARKETPLACE_DATA_DIR,
        help="Directory for self-play prediction/correction logs.",
    )
    parser.add_argument(
        "--output-dir",
        dest="logs_dir",
        type=Path,
        default=MARKETPLACE_DATA_DIR,
        help="Alias for --logs-dir.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    listings = _load_scraped_listings(args.input, args.max_examples)
    config = load_heuristics_config()

    predictions: List[Dict[str, Any]] = []
    corrections: List[Dict[str, Any]] = []

    for idx, listing in enumerate(listings, start=1):
        truth = _build_truth(listing)
        prediction = infer_listing(listing, config=config)
        example_id = f"selfplay-{idx:03d}"
        record = {
            "source": "selfplay",
            "example_id": example_id,
            "listing_id": listing.get("id"),
            "currency": "GBP",
            "prediction": prediction,
            "truth": truth,
            "logged_at": _timestamp(),
        }
        predictions.append(record)
        corrections.append(record)

    logs_dir = args.logs_dir
    predictions_path = logs_dir / "selfplay_predictions.jsonl"
    corrections_path = logs_dir / "selfplay_corrections.jsonl"

    _write_jsonl(predictions, predictions_path)
    _write_jsonl(corrections, corrections_path)

    print(f"Wrote {len(predictions)} predictions to {predictions_path}")
    print(f"Wrote {len(corrections)} corrections to {corrections_path}")


if __name__ == "__main__":
    main()
