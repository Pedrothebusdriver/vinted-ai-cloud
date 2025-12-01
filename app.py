import copy
import json
import json
import math
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

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

drafts: Dict[int, Dict[str, Any]] = {}
_next_draft_id = 1

SAMPLE_BRANDS = ["Nike", "Adidas", "Zara", "H&M", "Uniqlo", "Levi's"]
SAMPLE_COLOURS = ["Black", "Blue", "Charcoal", "Green", "Grey", "Red", "White"]
SAMPLE_ITEMS = ["Hoodie", "Jacket", "Jeans", "T-Shirt", "Dress", "Sweater"]

LEARNING_DATA_DIR = Path("tools/marketplace_eval/data")
LEARNING_DATA_DIR.mkdir(parents=True, exist_ok=True)
USER_CORRECTIONS_LOG = LEARNING_DATA_DIR / "user_corrections.jsonl"

def _now_iso() -> str:
    return datetime.utcnow().isoformat()

def _rng_for_name(name: str) -> random.Random:
    seed = abs(hash(name or time.time())) % (10**9)
    return random.Random(seed)

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
        }
        with USER_CORRECTIONS_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        # Best-effort logging; avoid breaking API on logging failure.
        pass

def _save_upload(file_storage) -> Dict[str, str]:
    filename = secure_filename(file_storage.filename or "upload.jpg")
    stamped = f"{int(time.time() * 1000)}_{filename}"
    target = UPLOAD_DIR / stamped
    file_storage.save(target)
    return {
        "filename": stamped,
        "path": str(target),
        "url": f"/uploads/{stamped}",
    }

def _create_draft(files: List, metadata: Dict[str, Any]) -> Dict[str, Any]:
    global _next_draft_id
    if not files:
        raise ValueError("No files provided")

    saved_files = [_save_upload(f) for f in files]
    attrs = _infer_attributes_from_filename(files[0].filename)

    brand = _clean_value(metadata.get("brand"), attrs["brand"])
    colour = _clean_value(metadata.get("colour"), attrs["colour"])
    size = _clean_value(metadata.get("size"), attrs["size"])
    condition = _clean_value(metadata.get("condition"), "Good")
    status = _clean_value(metadata.get("status"), "draft")
    title = _clean_value(metadata.get("title"), attrs["title"])
    description = _clean_value(
        metadata.get("description"), f"{title} in {condition} condition."
    )

    price_mid = _coerce_price(metadata.get("price_mid"), attrs["price_mid"])
    price_low = _coerce_price(metadata.get("price_low"), attrs["price_low"])
    price_high = _coerce_price(metadata.get("price_high"), attrs["price_high"])
    selected_price = metadata.get("selected_price")

    draft_id = _next_draft_id
    _next_draft_id += 1
    now = _now_iso()

    photos = [
        {
            "id": idx + 1,
            "url": saved["url"],
            "filename": saved["filename"],
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
        "cover_photo_url": photos[0]["url"] if photos else None,
        "thumbnail_url": photos[0]["url"] if photos else None,
        "created_at": now,
        "updated_at": now,
        "raw_attributes": attrs,
    }
    drafts[draft_id] = draft
    return draft

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
    try:
        draft = _create_draft(files, metadata)
    except Exception as exc:  # pragma: no cover - simple guardrail
        return jsonify({"error": str(exc) or "unable to create draft"}), 400
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


@app.put("/api/drafts/<int:draft_id>")
def update_draft(draft_id: int):
    draft = drafts.get(draft_id)
    if not draft:
        return jsonify({"error": "draft not found"}), 404

    before = copy.deepcopy(draft)
    data = request.get_json(silent=True) or {}
    updated = False

    for field in ("title", "description", "status"):
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
    return jsonify(draft)


@app.get("/health")
def health():
    return jsonify({"ok": True, "vinted_base": VINTED_BASE})

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
