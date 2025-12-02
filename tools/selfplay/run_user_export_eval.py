"""
Generate prediction/correction logs from Pete's Vinted personal export.

Outputs JSONL to:
- tools/marketplace_eval/data/user_export_predictions.jsonl
- tools/marketplace_eval/data/user_export_corrections.jsonl
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from inference_core import infer_listing, load_heuristics_config  # noqa: E402
from tools.datasets import load_vinted_export  # noqa: E402

MARKETPLACE_DATA_DIR = CURRENT_FILE.parents[1] / "marketplace_eval" / "data"
DEFAULT_EXPORT = REPO_ROOT / "data" / "raw" / "vinted_export_20251202.zip"


def _write_jsonl(records: Iterable[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _build_truth(listing: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": listing.get("title_truth") or "",
        "description": listing.get("description_truth") or "",
        "brand": listing.get("brand_truth"),
        "size": listing.get("size_truth"),
        "colour": listing.get("colour_truth"),
        "condition": listing.get("condition_truth"),
        "category": listing.get("category_truth"),
        "price_gbp": listing.get("price_gbp_truth"),
        "currency": "GBP",
    }


def _build_listing_input(listing: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": listing.get("title_truth") or "",
        "description": listing.get("description_truth") or "",
        "brand": listing.get("brand_truth"),
        "size": listing.get("size_truth"),
        "colour": listing.get("colour_truth"),
        "condition": listing.get("condition_truth"),
        "category": listing.get("category_truth"),
        "price_gbp": listing.get("price_gbp_truth"),
        "currency": "GBP",
    }


def _slice_listings(listings: List[Dict[str, Any]], limit: Optional[int]) -> List[Dict[str, Any]]:
    if limit is None or limit <= 0:
        return listings
    return listings[:limit]


def _build_records(
    listings: List[Dict[str, Any]], config: Dict[str, Any]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    predictions: List[Dict[str, Any]] = []
    corrections: List[Dict[str, Any]] = []
    for idx, listing in enumerate(listings, start=1):
        truth = _build_truth(listing)
        prediction = infer_listing(_build_listing_input(listing), config=config)
        example_id = f"user-export-{idx:04d}"
        record = {
            "source": "user_export",
            "example_id": example_id,
            "listing_id": listing.get("listing_id"),
            "currency": "GBP",
            "prediction": prediction,
            "truth": truth,
            "url": listing.get("url"),
            "image_urls": listing.get("image_urls"),
        }
        predictions.append(record)
        corrections.append(record)
    return predictions, corrections


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run heuristics over the Vinted export.")
    parser.add_argument(
        "--export-path",
        type=Path,
        default=DEFAULT_EXPORT,
        help="Path to Pete's Vinted export (ZIP or CSV).",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=None,
        help="Optional cap on number of listings.",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=MARKETPLACE_DATA_DIR,
        help="Directory for prediction/correction JSONL output.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    listings = load_vinted_export(str(args.export_path))
    listings = _slice_listings(listings, args.max_examples)
    config = load_heuristics_config()

    predictions, corrections = _build_records(listings, config)

    predictions_path = args.logs_dir / "user_export_predictions.jsonl"
    corrections_path = args.logs_dir / "user_export_corrections.jsonl"

    _write_jsonl(predictions, predictions_path)
    _write_jsonl(corrections, corrections_path)

    print(f"Wrote {len(predictions)} predictions to {predictions_path}")
    print(f"Wrote {len(corrections)} corrections to {corrections_path}")


if __name__ == "__main__":
    main()
