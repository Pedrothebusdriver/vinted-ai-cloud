import math
import os
import random
import re
import time
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, request

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

def mk_session() -> requests.Session:
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

    # 2) Fallback HTML if empty
    source = "api"
    if not items:
        time.sleep(0.4)
        items = fetch_vinted_html(q, sess)
        source = "html"

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

if __name__ == "__main__":
    # Local debug: Render runs via gunicorn, so this is ignored there
    port = int(os.getenv("PORT", "5055"))
    app.run(host="0.0.0.0", port=port, debug=False)
