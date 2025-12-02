"""
Lightweight scraper (with a built-in fallback) to produce Vinted-style listings for self-play.

Outputs JSONL to tools/selfplay/data/scraped_listings.jsonl.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests.exceptions import RequestException


CURRENT_FILE = Path(__file__).resolve()
DATA_DIR = CURRENT_FILE.parent / "data"
DEFAULT_OUTPUT = DATA_DIR / "scraped_listings.jsonl"

# UK-flavoured placeholder listings to guarantee GBP-only data.
PLACEHOLDER_LISTINGS: List[Dict[str, Any]] = [
    {
        "id": "placeholder-001",
        "title": "Nike blue hoodie size L",
        "description": "Men's Nike pullover hoodie, blue, size L, good used condition.",
        "brand": "Nike",
        "size": "L",
        "colour": "Blue",
        "condition": "Good used",
        "category": "Hoodie",
        "price_gbp": 18.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-002",
        "title": "Adidas black track jacket",
        "description": "Adidas originals track jacket in black, size M, lightly worn.",
        "brand": "Adidas",
        "size": "M",
        "colour": "Black",
        "condition": "Good used",
        "category": "Jacket",
        "price_gbp": 28.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-003",
        "title": "Barbour wax jacket size 14",
        "description": "Classic Barbour waxed jacket, olive green, women's UK 14, excellent condition.",
        "brand": "Barbour",
        "size": "UK 14",
        "colour": "Green",
        "condition": "Excellent",
        "category": "Jacket",
        "price_gbp": 95.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-004",
        "title": "Levi's 501 jeans W32 L32",
        "description": "Levi's 501 straight fit jeans, mid-wash blue, W32 L32, gently worn.",
        "brand": "Levi's",
        "size": "W32 L32",
        "colour": "Blue",
        "condition": "Good used",
        "category": "Jeans",
        "price_gbp": 38.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-005",
        "title": "Dr. Martens 1460 boots UK 8",
        "description": "Black leather Dr. Martens 1460 boots, UK size 8, broken in but tidy.",
        "brand": "Dr. Martens",
        "size": "UK 8",
        "colour": "Black",
        "condition": "Used",
        "category": "Boots",
        "price_gbp": 70.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-006",
        "title": "COS wool coat charcoal",
        "description": "COS long wool blend coat in charcoal grey, size M, great for winter.",
        "brand": "COS",
        "size": "M",
        "colour": "Grey",
        "condition": "Excellent",
        "category": "Coat",
        "price_gbp": 120.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-007",
        "title": "Zara floral midi dress",
        "description": "Zara floral print midi dress, UK size 10, worn once to a wedding.",
        "brand": "Zara",
        "size": "UK 10",
        "colour": "Multi",
        "condition": "Excellent",
        "category": "Dress",
        "price_gbp": 32.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-008",
        "title": "North Face puffer jacket",
        "description": "The North Face 700 fill down puffer, navy, size L, very warm.",
        "brand": "The North Face",
        "size": "L",
        "colour": "Navy",
        "condition": "Good used",
        "category": "Coat",
        "price_gbp": 110.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-009",
        "title": "Hunter wellies size 6",
        "description": "Hunter original tall wellies, dark green, UK 6, muddy but solid.",
        "brand": "Hunter",
        "size": "UK 6",
        "colour": "Green",
        "condition": "Used",
        "category": "Boots",
        "price_gbp": 42.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-010",
        "title": "Reiss tailored blazer 40R",
        "description": "Reiss slim-fit navy blazer, 40R, barely worn, sharp condition.",
        "brand": "Reiss",
        "size": "40R",
        "colour": "Navy",
        "condition": "Excellent",
        "category": "Blazer",
        "price_gbp": 85.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-011",
        "title": "Patagonia Better Sweater",
        "description": "Patagonia Better Sweater fleece, grey, men's M, lightly worn.",
        "brand": "Patagonia",
        "size": "M",
        "colour": "Grey",
        "condition": "Good used",
        "category": "Fleece",
        "price_gbp": 55.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-012",
        "title": "Uniqlo down gilet",
        "description": "Uniqlo ultra light down gilet, black, size S, great for layering.",
        "brand": "Uniqlo",
        "size": "S",
        "colour": "Black",
        "condition": "Good used",
        "category": "Gilet",
        "price_gbp": 25.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-013",
        "title": "New Balance 990v5 UK 9",
        "description": "New Balance 990v5 trainers, grey, UK 9, lightly worn with box.",
        "brand": "New Balance",
        "size": "UK 9",
        "colour": "Grey",
        "condition": "Excellent",
        "category": "Trainers",
        "price_gbp": 95.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-014",
        "title": "Arket merino jumper",
        "description": "Arket merino wool crew neck jumper, oatmeal, size M, soft feel.",
        "brand": "Arket",
        "size": "M",
        "colour": "Beige",
        "condition": "Excellent",
        "category": "Knitwear",
        "price_gbp": 40.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-015",
        "title": "Lululemon Align leggings",
        "description": "Lululemon Align leggings 25\", black, size 6 (UK 10), squat-proof.",
        "brand": "Lululemon",
        "size": "UK 10",
        "colour": "Black",
        "condition": "Excellent",
        "category": "Leggings",
        "price_gbp": 48.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-016",
        "title": "AllSaints biker jacket",
        "description": "AllSaints Balfern leather biker jacket, black, UK 8, well-loved.",
        "brand": "AllSaints",
        "size": "UK 8",
        "colour": "Black",
        "condition": "Good used",
        "category": "Jacket",
        "price_gbp": 150.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-017",
        "title": "Ted Baker suit trousers 34R",
        "description": "Ted Baker navy suit trousers, 34R, sharp crease, worn twice.",
        "brand": "Ted Baker",
        "size": "34R",
        "colour": "Navy",
        "condition": "Excellent",
        "category": "Trousers",
        "price_gbp": 55.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-018",
        "title": "Clarks desert boots UK 10",
        "description": "Clarks desert boots in sand suede, UK 10, gently worn.",
        "brand": "Clarks",
        "size": "UK 10",
        "colour": "Sand",
        "condition": "Good used",
        "category": "Boots",
        "price_gbp": 52.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-019",
        "title": "Finisterre waterproof shell",
        "description": "Finisterre waterproof shell jacket, burnt orange, size L, ready for rain.",
        "brand": "Finisterre",
        "size": "L",
        "colour": "Orange",
        "condition": "Excellent",
        "category": "Jacket",
        "price_gbp": 130.0,
        "currency": "GBP",
    },
    {
        "id": "placeholder-020",
        "title": "Mulberry small Bayswater",
        "description": "Mulberry small Bayswater tote in oak leather, lightly used, dustbag included.",
        "brand": "Mulberry",
        "size": None,
        "colour": "Brown",
        "condition": "Good used",
        "category": "Bag",
        "price_gbp": 260.0,
        "currency": "GBP",
    },
]


def _extract_price_gbp(raw_price: Any) -> Optional[float]:
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return float(raw_price)
    if isinstance(raw_price, dict):
        amount = raw_price.get("amount") or raw_price.get("value") or raw_price.get("number")
        try:
            return float(amount) if amount is not None else None
        except (TypeError, ValueError):
            return None
    try:
        return float(raw_price)
    except (TypeError, ValueError):
        return None


def _to_nullable_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str if value_str else None


def _normalise_listing(raw: Dict[str, Any], fallback_index: int) -> Optional[Dict[str, Any]]:
    price_block = raw.get("price") if isinstance(raw, dict) else None
    currency = None
    if isinstance(price_block, dict):
        currency = price_block.get("currency_code") or price_block.get("currency")
    elif isinstance(raw, dict):
        currency = raw.get("currency_code") or raw.get("currency")

    if currency and str(currency).upper() != "GBP":
        return None

    price_gbp = _extract_price_gbp(price_block or raw.get("price"))
    listing_id = str(raw.get("id") or f"fetched-{fallback_index}")
    title = _to_nullable_str(
        raw.get("title") or raw.get("brand_title") or raw.get("catalog_title") or raw.get("name")
    ) or "Vinted listing"
    description = _to_nullable_str(raw.get("description")) or "Listing pulled from Vinted UK search."

    return {
        "id": listing_id,
        "title": title,
        "description": description,
        "brand": _to_nullable_str(raw.get("brand_title") or raw.get("brand")),
        "size": _to_nullable_str(raw.get("size_title") or raw.get("size")),
        "colour": _to_nullable_str(raw.get("color") or raw.get("colour")),
        "condition": _to_nullable_str(raw.get("condition") or raw.get("state")),
        "category": _to_nullable_str(raw.get("catalog_name") or raw.get("category_name")),
        "price_gbp": price_gbp,
        "currency": "GBP",
        "scraped_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def _fallback_listings(max_listings: int) -> List[Dict[str, Any]]:
    listings: List[Dict[str, Any]] = []
    for idx in range(max_listings):
        template = PLACEHOLDER_LISTINGS[idx % len(PLACEHOLDER_LISTINGS)].copy()
        template["id"] = f"{template['id']}-{idx}"
        template["scraped_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        listings.append(template)
    return listings


def fetch_vinted_listings(max_listings: int) -> List[Dict[str, Any]]:
    """
    Attempt to fetch listings from the public Vinted UK catalog endpoint.
    Falls back to placeholder data if anything goes wrong.
    """
    per_page = max(1, min(max_listings, 100))
    url = "https://www.vinted.co.uk/api/v2/catalog/items"
    params = {"page": 1, "per_page": per_page, "search_text": "jacket", "currency": "GBP"}
    headers = {"User-Agent": "selfplay-scraper/0.2"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code in (401, 403, 404, 408, 429, 500, 502, 503, 504):
            raise RequestException(f"HTTP {response.status_code}")
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items") or []
        listings: List[Dict[str, Any]] = []
        for idx, item in enumerate(items[:max_listings]):
            normalised = _normalise_listing(item, idx)
            if normalised:
                listings.append(normalised)
        if listings:
            return listings
        print("No GBP listings returned from Vinted UK; using placeholder examples.")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch live Vinted UK data ({exc}); using placeholder examples.")

    return _fallback_listings(max_listings)


def _write_jsonl(records: Iterable[Dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape (or synthesise) Vinted UK listings.")
    parser.add_argument(
        "--max-listings",
        type=int,
        default=100,
        help="Maximum number of listings to collect.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch/synthesise listings but do not write the output file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output path for the scraped listings (default: {DEFAULT_OUTPUT}).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    listings = fetch_vinted_listings(args.max_listings)

    if args.dry_run:
        preview = listings[: min(3, len(listings))]
        print(json.dumps(preview, indent=2))
        print(f"[dry-run] Generated {len(listings)} listings; no file written.")
        return

    _write_jsonl(listings, args.output)
    print(f"Wrote {len(listings)} GBP listings to {args.output}")


if __name__ == "__main__":
    main()
