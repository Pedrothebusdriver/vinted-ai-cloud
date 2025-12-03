import copy
import json
import math
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from tools.image_grouping import PhotoSample, compute_phash, group_photos_by_content

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None

from inference_core import infer_listing, load_heuristics_config

try:
    import cloudscraper
except ImportError:  # pragma: no cover - optional dependency
    cloudscraper = None

# =========================
# Config (env overrides)
# =========================
VINTED_BASE = os.getenv("VINTED_BASE", "https://www.vinted.co.uk").rstrip("/")
CONNECT_TIMEOUT = float(os.getenv("CONNECT_TIMEOUT", "5"))
READ_TIMEOUT = float(os.getenv("READ_TIMEOUT", "15"))
DEFAULT_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

MAX_ITEMS = int(os.getenv("MAX_ITEMS", "40"))           # cap results for memory/speed
EXAMPLES_LIMIT = int(os.getenv("EXAMPLES_LIMIT", "5"))   # how many examples to return
CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))           # seconds
ENABLE_OUTLIER_FILTER = os.getenv("OUTLIER_FILTER", "1") == "1"
# Optional soft clamp (drop obviously silly prices from HTML scraping)
CLAMP_MIN = float(os.getenv("CLAMP_MIN", "2"))
CLAMP_MAX = float(os.getenv("CLAMP_MAX", "500"))
# Bulk grouping heuristics (mirrors mobile grouping).
BULK_GROUP_TIME_GAP_SECONDS = int(os.getenv("BULK_GROUP_TIME_GAP_SECONDS", "20"))
BULK_MAX_PHOTOS_PER_DRAFT = int(os.getenv("BULK_MAX_PHOTOS_PER_DRAFT", "8"))
BULK_PHASH_THRESHOLD = int(os.getenv("BULK_PHASH_THRESHOLD", "10"))
BULK_FALLBACK_TIME_GAP_SECONDS = float(os.getenv("BULK_FALLBACK_TIME_GAP_SECONDS", str(5 * 60)))
# NOTE: Bulk grouping now relies on perceptual hashing for content similarity, with a small
# fallback time-gap split when photos are extremely far apart in time.

UA_LIST = [
    # tiny + realistic; rotated to avoid being blocked
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Mobile Safari/537.36"
    ),
]

# tiny in-memory cache with TTL (kept simple on purpose)
_cache: Dict[str, Any] = {}  # key -> {"t": timestamp, "data": dict}

app = Flask(__name__)

# =========================
# Draft store (in-memory)
# =========================
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
THUMB_DIR = UPLOAD_DIR / "thumbs"
THUMB_DIR.mkdir(parents=True, exist_ok=True)
DRAFT_STATE_PATH = Path(os.getenv("DRAFT_STATE_PATH", "data/drafts.json"))

drafts: Dict[int, Dict[str, Any]] = {}
_next_draft_id = 1

def _load_drafts_from_disk():
    global drafts, _next_draft_id
    if not DRAFT_STATE_PATH.exists():
        return
    try:
        data = json.loads(DRAFT_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            drafts = {int(k): v for k, v in data.items()}
            if drafts:
                _next_draft_id = max(drafts.keys()) + 1
    except Exception:
        pass

def _persist_drafts():
    try:
        DRAFT_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with DRAFT_STATE_PATH.open("w", encoding="utf-8") as f:
            json.dump(drafts, f)
    except Exception:
        pass

_load_drafts_from_disk()
SAMPLE_BRANDS = ["Nike", "Adidas", "Zara", "H&M", "Uniqlo", "Levi's"]
SAMPLE_COLOURS = ["Black", "Blue", "Charcoal", "Green", "Grey", "Red", "White"]
SAMPLE_ITEMS = ["Hoodie", "Jacket", "Jeans", "T-Shirt", "Dress", "Sweater"]

LEARNING_DATA_DIR = Path("tools/marketplace_eval/data")
LEARNING_DATA_DIR.mkdir(parents=True, exist_ok=True)
USER_CORRECTIONS_LOG = LEARNING_DATA_DIR / "user_corrections.jsonl"
USER_PREDICTIONS_LOG = LEARNING_DATA_DIR / "user_predictions.jsonl"
HEURISTICS_CONFIG_PATH = Path("auto_heuristics_config.json")
_HEURISTICS_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_HEURISTICS_CONFIG_MTIME: Optional[float] = None

def _now_iso() -> str:
    return datetime.utcnow().isoformat()

def _rng_for_name(name: str) -> random.Random:
    seed = abs(hash(name or time.time())) % (10**9)
    return random.Random(seed)

def _load_heuristics_config() -> Dict[str, Any]:
    global _HEURISTICS_CONFIG_CACHE, _HEURISTICS_CONFIG_MTIME
    try:
        mtime = HEURISTICS_CONFIG_PATH.stat().st_mtime
    except FileNotFoundError:
        return load_heuristics_config()
    if _HEURISTICS_CONFIG_CACHE is None or _HEURISTICS_CONFIG_MTIME != mtime:
        _HEURISTICS_CONFIG_CACHE = load_heuristics_config(HEURISTICS_CONFIG_PATH)
        _HEURISTICS_CONFIG_MTIME = mtime
    return _HEURISTICS_CONFIG_CACHE or load_heuristics_config()

def _infer_attributes_from_filename(filename: str) -> Dict[str, Any]:
    base = os.path.splitext(filename or "Item")[0]
    tokens = [t for t in re.split(r"[\s_\-]+", base) if t]
    rng = _rng_for_name(base)

    brand = next((t.title() for t in tokens if len(t) > 2), None) or rng.choice(SAMPLE_BRANDS)
    colour = rng.choice(SAMPLE_COLOURS)
    item_type = next((t.title() for t in tokens[1:]), None) or rng.choice(SAMPLE_ITEMS)
    title = " ".join(x for x in (brand, colour, item_type) if x)

    price_mid = rng.randint(12, 65)
    price_low = max(5, int(price_mid * 0.8))
    price_high = int(price_mid * 1.25)

    return dict(
        title=title or "Draft",
        brand=brand,
        colour=colour,
        size="M",
        item_type=item_type,
        price_mid=price_mid,
        price_low=price_low,
        price_high=price_high,
    )

def _parse_metadata(req) -> Dict[str, Any]:
    raw = req.form.get("metadata") or ""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}

def _clean_value(val: Any, default: str) -> str:
    if val is None:
        return default
    try:
        text = str(val).strip()
        return text or default
    except Exception:
        return default

def _coerce_price(val: Any, fallback: int) -> int:
    try:
        num = float(val)
        if num > 0:
            return int(num)
    except Exception:
        pass
    return int(fallback)

def _build_thumbnail(source_path: Path, filename: str) -> Dict[str, Optional[str]]:
    if Image is None:
        return {"thumb": None, "thumb_2x": None}
    try:
        img = Image.open(source_path).convert("RGB")
        width, height = img.size
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        crop = img.crop((left, top, left + size, top + size))
        thumb1 = crop.resize((400, 400))
        thumb2 = crop.resize((800, 800))
        target1 = THUMB_DIR / filename
        target2 = THUMB_DIR / f"@2x_{filename}"
        thumb1.save(target1, format="JPEG", quality=85)
        thumb2.save(target2, format="JPEG", quality=85)
        return {
            "thumb": f"/uploads/thumbs/{filename}",
            "thumb_2x": f"/uploads/thumbs/@2x_{filename}",
        }
    except Exception:
        return {"thumb": None, "thumb_2x": None}

def _extract_files(req) -> List:
    """Return all uploaded files, preserving the primary `file` first."""
    primary = req.files.getlist("file") or []
    extras = req.files.getlist("files") or []

    # Some clients send `file` as a single entry, so add it if not already present.
    single_primary = req.files.get("file")
    if single_primary and single_primary not in primary:
        primary = primary + [single_primary]

    seen = set()
    files: List = []
    for f in primary + extras:
        if not f:
            continue
        key = id(f)
        if key in seen:
            continue
        seen.add(key)
        files.append(f)
    return files

def _looks_like_kids(text: str) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in ["girl", "girls", "kid", "kids"]):
        return True
    return bool(re.search(r"\b\d-\d\b", lowered) or re.search(r"\bage\b", lowered))

def _build_title_description(
    brand: str,
    colour: str,
    size: str,
    condition: str,
    item_type: str,
    files: List,
) -> Tuple[str, str]:
    filenames = " ".join([getattr(f, "filename", "") or "" for f in files])
    brand_clean = (brand or "").strip()
    item = (item_type or "Item").strip()
    colour_clean = (colour or "Lovely").strip()
    size_clean = (size or "unspecified").strip()
    condition_clean = (condition or "good").strip()
    generic = "Girls" if (not brand_clean and _looks_like_kids(filenames)) else ""

    if brand_clean:
        title = f"{brand_clean} {item}".strip()
        desc_brand = brand_clean
    else:
        title = f"{generic} {item}".strip() if generic else item.title()
        desc_brand = generic or "Everyday"

    description = (
        f"{colour_clean} {desc_brand} {item} in {condition_clean} condition. "
        f"Size {size_clean}. Ideal for everyday wear."
    )
    return title, description

def _draft_snapshot(draft: Dict[str, Any]) -> Dict[str, Any]:
    keys = [
        "id",
        "title",
        "description",
        "brand",
        "size",
        "colour",
        "condition",
        "selected_price",
        "price_low",
        "price_mid",
        "price_high",
        "status",
    ]
    return {k: draft.get(k) for k in keys}

def log_user_correction(prediction: Optional[Dict[str, Any]], before: Dict[str, Any], after: Dict[str, Any]) -> None:
    try:
        LEARNING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "draft_id": after.get("id") or before.get("id"),
            "timestamp": _now_iso(),
            "prediction": prediction,
            "before": _draft_snapshot(before),
            "after": _draft_snapshot(after),
            "title": after.get("title") or before.get("title"),
            "description": after.get("description") or before.get("description"),
            "price_low": after.get("price_low"),
            "price_mid": after.get("price_mid"),
            "price_high": after.get("price_high"),
        }
        with USER_CORRECTIONS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        # Best-effort logging; avoid breaking API on logging failure.
        pass

def log_user_prediction(draft: Dict[str, Any]) -> None:
    try:
        LEARNING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "draft_id": draft.get("id"),
            "timestamp": _now_iso(),
            "title": draft.get("title"),
            "description": draft.get("description"),
            "price_low": draft.get("price_low"),
            "price_mid": draft.get("price_mid"),
            "price_high": draft.get("price_high"),
        }
        with USER_PREDICTIONS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        # Best-effort logging; avoid breaking API on logging failure.
        pass

def _save_upload(file_storage) -> Dict[str, str]:
    filename = secure_filename(file_storage.filename or "upload.jpg")
    now_ts = time.time()
    stamped = f"{int(now_ts * 1000)}_{filename}"
    target = UPLOAD_DIR / stamped
    file_storage.save(target)
    thumb_data = _build_thumbnail(target, stamped)
    return {
        "filename": stamped,
        "original_filename": filename,
        "path": str(target),
        "url": f"/uploads/{stamped}",
        "thumbnail_url": thumb_data.get("thumb") or f"/uploads/{stamped}",
        "thumbnail_url_2x": thumb_data.get("thumb_2x"),
        "saved_at": now_ts,
    }

def _price_hint_from_metadata(metadata: Dict[str, Any], fallback: Optional[float]) -> Optional[float]:
    for key in ("selected_price", "price_mid", "price"):
        val = metadata.get(key)
        try:
            if val is None:
                continue
            return float(val)
        except Exception:
            continue
    return float(fallback) if fallback is not None else None

def _build_inference_payload(
    metadata: Dict[str, Any], attrs: Dict[str, Any]
) -> Dict[str, Any]:
    price_hint = _price_hint_from_metadata(metadata, attrs.get("price_mid"))
    return {
        "title": metadata.get("title") or attrs.get("title"),
        "description": metadata.get("description"),
        "brand": metadata.get("brand") or attrs.get("brand"),
        "size": metadata.get("size") or attrs.get("size"),
        "colour": metadata.get("colour") or attrs.get("colour"),
        "condition": metadata.get("condition") or "Good",
        "category": metadata.get("category") or attrs.get("item_type"),
        "price_gbp": price_hint,
        "currency": "GBP",
    }

def _is_truthy_flag(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if val is None:
        return False
    try:
        text = str(val).strip().lower()
    except Exception:
        return False
    return text in ("1", "true", "yes", "y", "on")


def _should_use_bulk_grouping(metadata: Dict[str, Any]) -> bool:
    flags = [
        metadata.get("bulk"),
        metadata.get("bulk_mode"),
        metadata.get("bulk_upload"),
        metadata.get("bulkUpload"),
    ]
    try:
        flags.append(request.args.get("bulk"))
    except Exception:
        pass
    return any(_is_truthy_flag(flag) for flag in flags)


def _create_draft_from_saved_files(saved_files: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
    global _next_draft_id
    if not saved_files:
        raise ValueError("No files provided")

    primary_name = (
        saved_files[0].get("original_filename") or saved_files[0].get("filename") or "upload.jpg"
    )
    attrs = _infer_attributes_from_filename(primary_name)
    status = _clean_value(metadata.get("status"), "draft")

    heuristic_payload = _build_inference_payload(metadata, attrs)
    try:
        prediction = infer_listing(heuristic_payload, config=_load_heuristics_config())
    except Exception:
        prediction = {}

    brand = _clean_value(metadata.get("brand"), prediction.get("brand") or attrs["brand"])
    colour = _clean_value(metadata.get("colour"), prediction.get("colour") or attrs["colour"])
    size = _clean_value(metadata.get("size"), prediction.get("size") or attrs["size"])
    condition = _clean_value(metadata.get("condition"), prediction.get("condition") or "Good")

    title = _clean_value(metadata.get("title"), prediction.get("title") or attrs["title"])
    description = _clean_value(
        metadata.get("description"),
        prediction.get("description") or f"{title} in {condition} condition.",
    )

    price_mid_infer = prediction.get("price_gbp")
    price_mid = max(1, _coerce_price(metadata.get("price_mid"), price_mid_infer or attrs["price_mid"]))
    price_low = max(1, _coerce_price(metadata.get("price_low"), int(price_mid * 0.9)))
    price_high = max(price_low + 1, _coerce_price(metadata.get("price_high"), int(price_mid * 1.1)))
    selected_price = metadata.get("selected_price")

    draft_id = _next_draft_id
    _next_draft_id += 1
    now = _now_iso()

    photos = [
        {
            "id": idx + 1,
            "url": saved["url"],
            "filename": saved["filename"],
            "thumbnail_url": saved.get("thumbnail_url"),
            "thumbnail_url_2x": saved.get("thumbnail_url_2x"),
        }
        for idx, saved in enumerate(saved_files)
    ]

    draft = {
        "id": draft_id,
        "title": title,
        "brand": brand,
        "size": size,
        "colour": colour,
        "condition": condition,
        "status": status or "draft",
        "description": description,
        "price_low": price_low,
        "price_mid": price_mid,
        "price_high": price_high,
        "selected_price": selected_price,
        "photos": photos,
        "photo_count": len(photos),
        "cover_photo_url": photos[0].get("url") if photos else None,
        "thumbnail_url": photos[0].get("thumbnail_url") if photos else None,
        "created_at": now,
        "updated_at": now,
        "raw_attributes": attrs,
    }
    drafts[draft_id] = draft
    _persist_drafts()
    return draft


def _create_draft(files: List, metadata: Dict[str, Any]) -> Dict[str, Any]:
    if not files:
        raise ValueError("No files provided")

    saved_files = [_save_upload(f) for f in files]
    return _create_draft_from_saved_files(saved_files, metadata)


def _build_photo_samples(saved_files: List[Dict[str, Any]]) -> List[PhotoSample]:
    samples: List[PhotoSample] = []
    for idx, saved in enumerate(saved_files):
        taken_at = saved.get("taken_at")
        if taken_at is None:
            saved_at = saved.get("saved_at")
            if saved_at is not None:
                try:
                    taken_at = float(saved_at)
                except Exception:
                    taken_at = None
        samples.append(PhotoSample(id=idx, path=saved["path"], taken_at=taken_at))
    return samples


def _create_bulk_drafts(files: List, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not files:
        return []

    saved_files = [_save_upload(f) for f in files]
    samples = _build_photo_samples(saved_files)

    groups = group_photos_by_content(
        samples,
        max_photos_per_group=BULK_MAX_PHOTOS_PER_DRAFT,
        hash_threshold=BULK_PHASH_THRESHOLD,
        fallback_time_gap_seconds=BULK_FALLBACK_TIME_GAP_SECONDS,
    )

    try:
        summary_msg = f"[bulk_grouping] photos={len(samples)} groups={len(groups)}"
        app.logger.info(summary_msg)
        print(summary_msg, flush=True)
        for idx, group in enumerate(groups):
            rep_hash = None
            if group:
                try:
                    rep_hash = str(compute_phash(group[0].path))
                except Exception:
                    rep_hash = "error"
            detail = f"[bulk_grouping] group {idx} size={len(group)} representative_hash={rep_hash}"
            app.logger.info(detail)
            print(detail, flush=True)
    except Exception:
        pass

    drafts_created: List[Dict[str, Any]] = []
    for group in groups:
        mapped_files: List[Dict[str, Any]] = []
        for sample in group:
            try:
                mapped_files.append(saved_files[int(sample.id)])
            except Exception:
                continue
        if not mapped_files:
            continue
        draft = _create_draft_from_saved_files(mapped_files, metadata)
        drafts_created.append(draft)
    return drafts_created

def _filtered_drafts(req) -> List[Dict[str, Any]]:
    status = (req.args.get("status") or "").strip().lower()
    brand = (req.args.get("brand") or "").strip().lower()
    size = (req.args.get("size") or "").strip().lower()

    items = list(drafts.values())
    items.sort(key=lambda d: d.get("updated_at", ""), reverse=True)

    def _matches(d: Dict[str, Any]) -> bool:
        if status and (d.get("status") or "").lower() != status:
            return False
        if brand and brand not in (d.get("brand") or "").lower():
            return False
        if size and size not in (d.get("size") or "").lower():
            return False
        return True

    items = [d for d in items if _matches(d)]
    limit = req.args.get("limit")
    offset = req.args.get("offset")
    try:
        limit_val = max(1, min(int(limit), 100)) if limit else len(items)
    except Exception:
        limit_val = len(items)
    try:
        offset_val = max(0, int(offset)) if offset else 0
    except Exception:
        offset_val = 0
    return items[offset_val : offset_val + limit_val]

# =========================
# Math helpers
# =========================
def pct(values: List[float], p: float) -> Optional[float]:
    if not values:
        return None
    arr = sorted(values)
    k = (len(arr) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(arr[int(k)])
    d0 = arr[int(f)] * (c - k)
    d1 = arr[int(c)] * (k - f)
    return float(d0 + d1)

def median(values: List[float]) -> Optional[float]:
    return pct(values, 50)

def iqr_filter(vals: List[float]) -> List[float]:
    """Trim extreme outliers with 1.5*IQR; keeps stats stable."""
    if len(vals) < 6:
        return vals
    q1 = pct(vals, 25)
    q3 = pct(vals, 75)
    if q1 is None or q3 is None:
        return vals
    iqr = q3 - q1
    lo = q1 - 1.5 * iqr
    hi = q3 + 1.5 * iqr
    return [v for v in vals if lo <= v <= hi]

# =========================
# Parse & normalize helpers
# =========================
def normalize_query(brand: str, item_type: str, size: str, colour: str) -> str:
    parts = [x.strip() for x in (brand, item_type, size, colour) if x and x.strip()]
    q = " ".join(parts)
    return " ".join(q.split())

# Strict currency finder (prefers £... then ...GBP)
CURRENCY_RXES = [
    re.compile(r"£\s*([0-9][0-9\s,\.]*)", re.IGNORECASE),
    re.compile(r"([0-9][0-9\s,\.]*)\s*GBP\b", re.IGNORECASE),
]

def _normalize_amount_string(s: str) -> Optional[float]:
    """Normalise strings like '1,299.00', '47,95', '4795', '71.08 1' -> float GBP."""
    if not s:
        return None
    s = s.strip().replace("\u00A0", " ")  # NBSP -> space

    # Remove surrounding junk
    s = s.strip()

    # If comma present and dot absent -> comma likely decimal separator (e.g., 47,95)
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    else:
        # Else drop commas as thousand separators (1,299.00)
        s = s.replace(",", "")

    # Keep digits + at most one dot
    cleaned = []
    dot = False
    for ch in s:
        if ch.isdigit():
            cleaned.append(ch)
        elif ch == "." and not dot:
            cleaned.append(".")
            dot = True
        # else ignore

    s2 = "".join(cleaned)
    if not s2:
        return None

    try:
        v = float(s2)
        # If no dot originally and v is large like 4795 -> assume pence
        if "." not in s2 and v >= 1000:
            v = v / 100.0
        if 0 < v < 10000:
            return round(v, 2)
    except Exception:
        return None
    return None

def extract_price_from_text(text: Optional[str]) -> Optional[float]:
    """Pick the FIRST currency-looking amount, prefer '£...'. Avoids concatenation mistakes."""
    if not text:
        return None
    for rx in CURRENCY_RXES:
        m = rx.search(text)
        if m:
            val = _normalize_amount_string(m.group(1))
            if val is not None:
                return val
    # Fallback: try a looser parse on the whole text
    return _normalize_amount_string(text)

def uniq(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for it in items:
        key = (it.get("url"), it.get("title"), it.get("price_gbp"))
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out

def mk_session(use_cloudscraper: bool = False):
    if use_cloudscraper and cloudscraper:
        s = cloudscraper.create_scraper()
    else:
        s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(UA_LIST),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s

# =========================
# Vinted fetchers
# =========================
def _coerce_price_gbp_from_api_item(it: Dict[str, Any]) -> Optional[float]:
    """
    API often returns minor units (pence). Convert to GBP when needed.
    Prefer string 'amount', then other fields; numeric may be pence.
    """
    pwc = it.get("price_with_currency")
    if isinstance(pwc, dict):
        amt = pwc.get("amount")
        if isinstance(amt, str):
            val = extract_price_from_text(amt)
            if val is not None:
                return val

    for key in ("price", "price_numeric", "total_item_price"):
        v = it.get(key)
        if isinstance(v, str):
            val = extract_price_from_text(v)
            if val is not None:
                return val

    for key in ("price", "price_numeric", "total_item_price"):
        v = it.get(key)
        if isinstance(v, (int, float)):
            num = float(v)
            if num >= 100:    # likely pence
                return round(num / 100.0, 2)
            if 0 < num < 10000:
                return round(num, 2)
    return None

def fetch_vinted_api(query: str, session: requests.Session) -> List[Dict[str, Any]]:
    """Try Vinted's JSON endpoint first (shape can change)."""
    results: List[Dict[str, Any]] = []
    api_urls = [
        f"{VINTED_BASE}/api/v2/catalog/items",
        f"{VINTED_BASE}/api/v2/catalog/items.json",
    ]
    params = {
        "search_text": query,
        "per_page": min(MAX_ITEMS, 40),
        "page": 1,
        "order": "newest_first",
        "currency": "GBP",
    }

    for url in api_urls:
        try:
            r = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
            if r.status_code != 200:
                continue
            data = r.json()
            items = data.get("items") or data.get("data") or []
            for it in items:
                title = (
                    it.get("title")
                    or it.get("description")
                    or it.get("brand_title")
                    or "Item"
                )
                price_gbp = _coerce_price_gbp_from_api_item(it)

                web_url = it.get("url") or it.get("path")
                if isinstance(web_url, str) and web_url.startswith("/"):
                    web_url = VINTED_BASE + web_url
                if not web_url:
                    iid = it.get("id")
                    if iid:
                        web_url = f"{VINTED_BASE}/items/{iid}"

                if price_gbp is not None:
                    results.append(
                        {
                            "title": str(title)[:120],
                            "price_gbp": price_gbp,
                            "url": web_url or VINTED_BASE,
                        }
                    )
            if results:
                break
        except Exception:
            continue
    return results[:MAX_ITEMS]

def fetch_vinted_html(query: str, session: requests.Session) -> List[Dict[str, Any]]:
    """Fallback: crawl search page and extract prices/titles/links with strict currency regex."""
    results: List[Dict[str, Any]] = []
    params = {"search_text": query, "order": "newest_first"}
    url = f"{VINTED_BASE}/catalog"
    try:
        r = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "html.parser")
        anchors = soup.select("a[href*='/items/']")
        for a in anchors[:MAX_ITEMS]:
            href = a.get("href")
            if not href:
                continue
            web_url = href if href.startswith("http") else (VINTED_BASE + href)

            # Prefer price near the card/anchor; search in progressively larger scopes
            candidate_texts = [
                a.get_text(" ", strip=True),
                a.parent.get_text(" ", strip=True) if a.parent else "",
                a.parent.parent.get_text(" ", strip=True) if a.parent and a.parent.parent else "",
            ]
            price_val: Optional[float] = None
            for txt in candidate_texts:
                pv = extract_price_from_text(txt)
                if pv is not None:
                    price_val = pv
                    break

            title = a.get("aria-label") or a.get_text(" ", strip=True) or "Item"
            if price_val is not None:
                results.append(
                    {
                        "title": title[:120],
                        "price_gbp": float(price_val),
                        "url": web_url,
                    }
                )
    except Exception:
        return results
    return results

# =========================
# Main comps computation
# =========================
def compute_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices = [x["price_gbp"] for x in items if isinstance(x.get("price_gbp"), (int, float))]
    raw = prices[:]

    # Soft clamp first to discard HTML misreads (e.g., £7,108.01)
    clamped = [v for v in prices if CLAMP_MIN <= v <= CLAMP_MAX]
    # If clamping kills too much, fall back to raw (we still have IQR below)
    prices = clamped if len(clamped) >= max(6, len(raw)//3) else raw

    if ENABLE_OUTLIER_FILTER:
        prices = iqr_filter(prices)

    if not prices:
        return dict(median=None, p25=None, p75=None, used_count=0, raw_count=len(raw), prices=[])

    return dict(
        median=round(median(prices), 2),
        p25=round(pct(prices, 25), 2),
        p75=round(pct(prices, 75), 2),
        used_count=len(prices),
        raw_count=len(raw),
        prices=prices,
    )

def get_comps(brand: str, item_type: str, size: str, colour: str) -> Dict[str, Any]:
    q = normalize_query(brand, item_type, size, colour)
    cache_key = f"q:{q}"
    now_ts = time.time()

    # serve from cache if fresh
    hit = _cache.get(cache_key)
    if hit and (now_ts - hit["t"] < CACHE_TTL):
        data = dict(hit["data"])
        data["cache"] = True
        return data

    sess = mk_session()

    # 1) Try API
    items = fetch_vinted_api(q, sess)
    source = "api"

    # 2) Fallback HTML if empty
    if not items:
        time.sleep(0.4)
        items = fetch_vinted_html(q, sess)
        source = "html"

    # 3) Cloudscraper retry if available and still empty
    if not items and cloudscraper:
        scraper_session = mk_session(use_cloudscraper=True)
        time.sleep(0.2)
        items = fetch_vinted_api(q, scraper_session)
        source = "cloudscraper-api"
        if not items:
            time.sleep(0.4)
            items = fetch_vinted_html(q, scraper_session)
            source = "cloudscraper-html" if items else source

    items = uniq(items)[:MAX_ITEMS]
    stats = compute_stats(items)

    examples = [
        {"title": it["title"], "price_gbp": round(it["price_gbp"], 2), "url": it["url"]}
        for it in items[:EXAMPLES_LIMIT]
    ]

    result = {
        "query": q,
        "count": stats["raw_count"],
        "median_price_gbp": stats["median"],
        "p25_gbp": stats["p25"],
        "p75_gbp": stats["p75"],
        "examples": examples,
        "source": source,
        "outlier_filter": ENABLE_OUTLIER_FILTER,
        "clamp": {"min": CLAMP_MIN, "max": CLAMP_MAX},
    }

    _cache[cache_key] = {"t": now_ts, "data": result}
    return result

# =========================
# Routes
# =========================
@app.route("/uploads/<path:filename>")
def serve_upload(filename: str):
    return send_from_directory(str(UPLOAD_DIR), filename)


@app.post("/process_image")
def process_image():
    files = _extract_files(request)
    if not files:
        return jsonify({"error": "file is required"}), 400
    metadata = _parse_metadata(request)
    bulk_mode = _should_use_bulk_grouping(metadata)
    try:
        if bulk_mode:
            drafts_created = _create_bulk_drafts(files, metadata)
            if not drafts_created:
                return jsonify({"error": "unable to create drafts"}), 400
            for draft in drafts_created:
                log_user_prediction(draft)
            log_msg = (
                f"[FlipLens] /process_image bulk photos={len(files)} drafts={len(drafts_created)}"
            )
            app.logger.info(log_msg)
            print(log_msg, flush=True)
            return jsonify({"drafts": drafts_created, "count": len(drafts_created)}), 201

        draft = _create_draft(files, metadata)
    except Exception as exc:  # pragma: no cover - simple guardrail
        return jsonify({"error": str(exc) or "unable to create draft"}), 400
    log_user_prediction(draft)
    log_msg = f"[FlipLens] /process_image received {len(files)} files, created draft {draft.get('id')}"
    app.logger.info(log_msg)
    print(log_msg, flush=True)
    return jsonify(draft), 201


@app.post("/api/drafts")
def create_draft_api():
    files = _extract_files(request)
    if not files:
        return jsonify({"error": "At least one file is required"}), 400
    metadata = _parse_metadata(request)
    draft = _create_draft(files, metadata)
    return jsonify(draft), 201


@app.get("/api/drafts")
def list_drafts():
    items = _filtered_drafts(request)
    return jsonify(items)


@app.get("/api/drafts/<int:draft_id>")
def get_draft(draft_id: int):
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify({"error": "draft not found"}), 404
    return jsonify(draft)


@app.put("/api/drafts/<int:draft_id>/photos")
def update_draft_photos(draft_id: int):
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify({"error": "draft not found"}), 404
    payload = request.get_json(silent=True) or {}
    photos = payload.get("photos")
    cover_url = payload.get("cover_photo_url")
    thumb_url = payload.get("thumbnail_url")
    thumb_url_2x = payload.get("thumbnail_url_2x")

    if photos and isinstance(photos, list):
        draft["photos"] = photos
    if cover_url:
        draft["cover_photo_url"] = cover_url
    if thumb_url:
        draft["thumbnail_url"] = thumb_url
    if thumb_url_2x:
        draft["thumbnail_url_2x"] = thumb_url_2x
    draft["updated_at"] = _now_iso()
    _persist_drafts()
    return jsonify(draft)


@app.put("/api/drafts/<int:draft_id>")
def update_draft(draft_id: int):
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify({"error": "draft not found"}), 404

    before = copy.deepcopy(draft)
    data = request.get_json(silent=True) or {}
    updated = False

    for field in (
        "title",
        "description",
        "status",
        "brand",
        "size",
        "colour",
        "condition",
        "thumbnail_url",
        "thumbnail_url_2x",
        "cover_photo_url",
    ):
        if field in data and data[field] is not None:
            draft[field] = data[field]
            updated = True

    if "price" in data and data["price"] is not None:
        try:
            draft["selected_price"] = float(data["price"])
            updated = True
        except Exception:
            pass

    if updated:
        draft["updated_at"] = _now_iso()
        changed_fields = [
            field
            for field in (
                "title",
                "description",
                "brand",
                "size",
                "colour",
                "condition",
                "selected_price",
                "price_low",
                "price_mid",
                "price_high",
                "status",
            )
            if before.get(field) != draft.get(field)
        ]
        if changed_fields:
            log_user_correction(prediction=None, before=before, after=draft)
        _persist_drafts()
    return jsonify(draft)


@app.get("/health")
def health():
    return jsonify({"ok": True, "vinted_base": VINTED_BASE})

@app.get("/")
def root():
    return jsonify({"status": "ok", "service": "vinted-ai-cloud", "docs": "/docs"})

def _params_from_request(req):
    brand = (req.args.get("brand") or "").strip()
    item_type = (req.args.get("item_type") or "").strip()
    size = (req.args.get("size") or "").strip()
    colour = (req.args.get("colour") or "").strip()
    return brand, item_type, size, colour

@app.get("/api/price")
def api_price():
    brand, item_type, size, colour = _params_from_request(request)
    data = get_comps(brand, item_type, size, colour)
    status = 200 if data.get("count") else 404
    return jsonify(data), status

@app.get("/price")  # simple fallback/alias
def price():
    return api_price()


@app.errorhandler(404)
def handle_404(_err):
    return jsonify({"detail": "Not found"}), 404


if __name__ == "__main__":
    # Local debug: Render runs via gunicorn, so this is ignored there
    port = int(os.getenv("PORT", "5055"))
    app.run(host="0.0.0.0", port=port, debug=False)
