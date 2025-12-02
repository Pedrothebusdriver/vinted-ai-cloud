"""
Loader for Pete's Vinted personal data export (HTML/CSV in ZIP).
"""

import csv
import io
import logging
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _parse_price(text: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    if not text:
        return None, None
    cleaned = str(text).strip()
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*([A-Za-z]{3})?", cleaned)
    if not match:
        return None, None
    amount = match.group(1).replace(",", "")
    try:
        value = float(amount)
    except ValueError:
        return None, match.group(2)
    currency = match.group(2) or None
    return value, currency


def _infer_listing_id(image_urls: List[str], fallback: int) -> str:
    for url in image_urls:
        match = re.search(r"/?photos/(\d+)/", url)
        if match:
            return match.group(1)
    return f"listing_{fallback}"


def _collect_image_urls(block, base: str = "listings") -> List[str]:
    urls: List[str] = []
    for img in block.find_all(attrs={"itemprop": "item_photo"}):
        src = img.get("src")
        if not src:
            continue
        normalised = src
        if not src.startswith("http") and base not in src:
            normalised = f"{base}/{src.lstrip('./')}"
        urls.append(normalised)
    return urls


def _text_for_itemprop(block, name: str) -> Optional[str]:
    node = block.find(attrs={"itemprop": name})
    if not node:
        return None
    text = node.get_text(strip=True)
    return text or None


def _parse_html_listings(raw_html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(raw_html, "lxml")
    blocks = soup.find_all("div", class_="cell", attrs={"itemscope": True})
    listings: List[Dict[str, Any]] = []
    for idx, block in enumerate(blocks):
        title = _text_for_itemprop(block, "title")
        description = _text_for_itemprop(block, "description")
        brand = _text_for_itemprop(block, "brand")
        size = _text_for_itemprop(block, "size")
        condition = _text_for_itemprop(block, "status")
        colour = _text_for_itemprop(block, "color")
        price_text = _text_for_itemprop(block, "order_value")
        created_at = _text_for_itemprop(block, "created_at")
        price_value, currency = _parse_price(price_text)

        image_urls = _collect_image_urls(block)
        listing_id = _infer_listing_id(image_urls, idx)

        price_gbp_truth = price_value if (currency is None or currency.upper() == "GBP") else None
        if currency and currency.upper() != "GBP":
            logger.warning("Non-GBP currency for listing %s: %s", listing_id, currency)

        listings.append(
            {
                "source": "user_export",
                "listing_id": str(listing_id),
                "title_truth": title,
                "description_truth": description,
                "brand_truth": brand,
                "size_truth": size,
                "colour_truth": colour,
                "condition_truth": condition,
                "category_truth": None,
                "price_gbp_truth": price_gbp_truth,
                "currency": "GBP",
                "url": None,
                "image_urls": image_urls,
                "created_at": created_at,
            }
        )
    return listings


def _parse_csv_listings(raw_csv: str) -> List[Dict[str, Any]]:
    listings: List[Dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(raw_csv))
    for idx, row in enumerate(reader):
        price_value, currency = _parse_price(row.get("price") or row.get("order_value") or "")
        price_gbp_truth = price_value if (currency is None or currency.upper() == "GBP") else None
        if currency and currency.upper() != "GBP":
            logger.warning("Non-GBP currency for CSV listing %s: %s", row.get("id") or idx, currency)

        listings.append(
            {
                "source": "user_export",
                "listing_id": str(row.get("id") or row.get("listing_id") or f"listing_{idx}"),
                "title_truth": row.get("title"),
                "description_truth": row.get("description"),
                "brand_truth": row.get("brand"),
                "size_truth": row.get("size"),
                "colour_truth": row.get("colour") or row.get("color"),
                "condition_truth": row.get("condition") or row.get("status"),
                "category_truth": row.get("category"),
                "price_gbp_truth": price_gbp_truth,
                "currency": "GBP",
                "url": row.get("url"),
                "image_urls": [],
                "created_at": row.get("created_at"),
            }
        )
    return listings


def _read_from_zip(path: Path) -> Tuple[Optional[str], Optional[str]]:
    with zipfile.ZipFile(path, "r") as archive:
        csv_member = None
        html_member = None
        for name in archive.namelist():
            lower = name.lower()
            if lower.endswith(".csv") and ("listing" in lower or "item" in lower):
                csv_member = name
                break
            if lower.endswith("listings/index.html"):
                html_member = name
        if csv_member:
            with archive.open(csv_member, "r") as handle:
                return handle.read().decode("utf-8"), "csv"
        if html_member:
            with archive.open(html_member, "r") as handle:
                return handle.read().decode("utf-8"), "html"
    return None, None


def load_vinted_export(path: str) -> List[Dict[str, Any]]:
    """
    Load Pete's Vinted export from `path` (ZIP or CSV) and return a list of normalized listing dicts.

    Normalized schema (all GBP where possible):
    {
        "source": "user_export",
        "listing_id": "<string id>",
        "title_truth": "<title>",
        "description_truth": "<description>",
        "brand_truth": "<brand or None>",
        "size_truth": "<size label or None>",
        "colour_truth": "<colour or None>",
        "condition_truth": "<condition label or None>",
        "category_truth": "<category path or label or None>",
        "price_gbp_truth": <float or None>,
        "currency": "GBP",
        "url": "<public listing URL if available or None>",
        "image_urls": ["...", ...]
    }
    """

    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Export file not found at {path}")

    raw_payload: Optional[str] = None
    payload_type: Optional[str] = None

    if path_obj.suffix.lower() == ".zip":
        raw_payload, payload_type = _read_from_zip(path_obj)
    elif path_obj.suffix.lower() == ".csv":
        raw_payload = path_obj.read_text(encoding="utf-8")
        payload_type = "csv"
    elif path_obj.suffix.lower() in {".html", ".htm"}:
        raw_payload = path_obj.read_text(encoding="utf-8")
        payload_type = "html"

    if raw_payload is None or payload_type is None:
        raise ValueError(f"Could not read export from {path}; ensure it is a ZIP with listings data.")

    if payload_type == "csv":
        return _parse_csv_listings(raw_payload)

    return _parse_html_listings(raw_payload)


__all__ = ["load_vinted_export"]
