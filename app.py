import os
import math
import time
import random
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

# =========================
# Config (env overrides)
# =========================
VINTED_BASE = os.getenv("VINTED_BASE", "https://www.vinted.co.uk").rstrip("/")
CONNECT_TIMEOUT = float(os.getenv("CONNECT_TIMEOUT", "5"))
READ_TIMEOUT = float(os.getenv("READ_TIMEOUT", "15"))
DEFAULT_TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

MAX_ITEMS = int(os.getenv("MAX_ITEMS", "40"))          # cap results for memory/speed
EXAMPLES_LIMIT = int(os.getenv("EXAMPLES_LIMIT", "5"))  # how many examples to return
CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))          # seconds
ENABLE_OUTLIER_FILTER = os.getenv("OUTLIER_FILTER", "1") == "1"

UA_LIST = [
    # tiny + realistic; rotated to avoid being blocked
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Mobile Safari/537.36",
]

# tiny in-memory cache with TTL (kept simple on purpose)
_cache: Dict[str, Any] = {}  # key -> {"t": timestamp, "data": dict}


# =========================
# Small math helpers
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


def parse_price(text: Optional[str]) -> Optional[float]:
    """Extract GBP float from messy text like '£12.50' or '12 GBP'."""
    if not text:
        return None
    t = text.replace(",", "").strip()
    if "£" in t:
        t = t.split("£", 1)[-1]
    if "GBP" in t.upper():
        t = t.upper().replace("GBP", "").strip()

    cleaned = []
    dot = False
    for ch in t:
        if ch.isdigit():
            cleaned.append(ch)
        elif ch == "." and not dot:
            cleaned.append(".")
            dot = True
        elif ch == " ":
            cleaned.append(" ")
    token = "".join(cleaned).strip().split()[-1] if cleaned else ""
    try:
        val = float(token)
        if 0 < val < 10000:
            return val
    except Exception:
        return None
    return None


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
    We try string 'amount' first; else handle numeric with a pence→GBP heuristic.
    """
    pwc = it.get("price_with_currency")
    if isinstance(pwc, dict):
        amt = pwc.get("amount")
        if isinstance(amt, str):
            parsed = parse_price(amt)
            if parsed is not None:
                return round(float(parsed), 2)

    for key in ("price", "price_numeric", "total_item_price"):
        val = it.get(key)
        if isinstance(val, str):
            parsed = parse_price(val)
            if parsed is not None:
                return round(float(parsed), 2)

    for key in ("price", "price_numeric", "total_item_price"):
        val = it.get(key)
        if isinstance(val, (int, float)):
            num = float(val)
            # Heuristic: if >= 100 it's likely pence; convert to GBP
            if num >= 100:
                return round(num / 100.0, 2)
            if 0 < num < 10000:
                return round(num, 2)

    return None


def fetch_vinted_api(query: str, session: requests.Session) -> List[Dict[str, Any]]:
    """
    Try Vinted's JSON endpoint first (shape can change).
    Returns list of {'title','price_gbp','url'}.
    """
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
                if web_url and isinstance(web_url, str) and web_url.startswith("/"):
                    web_url = VINTED_BASE + web_url
                if not web_url:
                    iid = it.get("id")
                    if iid:
                        web_url = f"{VINTED_BASE}/items/{iid}"

                if price_gbp is not None:
                    results.append({
                        "title": str(title)[:120],
                        "price_gbp": price_gbp,
                        "url": web_url or VINTED_BASE,
                    })
            if results:
                break
        except Exception:
            # Be resilient; fall back to HTML
            continue

    return results[:MAX_ITEMS]


def fetch_vinted_html(query: str, session: requests.Session) -> List[Dict[str, Any]]:
    """
    Fallback: crawl search page and extract prices/titles/links.
    """
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

            # Try to find a price text near the anchor
            price_text = None
            texts = [a.get_text(" ", strip=True)]
            parent = a.parent
            if parent:
                texts.append(parent.get_text(" ", strip=True))
                gp = parent.parent
                if gp:
                    texts.append(gp.get_text(" ", strip=True))
            for t in texts:
                if "£" in t or "GBP" in t.upper():
                    price_text = t
                    break
            price = parse_price(price_text)

            title = a.get("aria-label") or a.get_text(" ", strip=True) or "Item"
            if price:
                results.append({
                    "title": title[:120],
                    "price_gbp": float(round(price, 2)),
                    "url": web_url,
                })
    except Exception:
        return results

    return results


# =========================
# Main comps computation
# =========================
def compute_stats(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    prices = [x["price_gbp"] for x in items if isinstance(x.get("price_gbp"), (int, float))]
    if not prices:
        return dict(median=None, p25=None, p75=None, used_count=0, prices=[])

    raw = prices[:]
    if ENABLE_OUTLIER_FILTER:
        prices = iqr_filter(prices)

    return dict(
        median=round(median(prices), 2) if prices else None,
        p25=round(pct(prices, 25), 2) if prices else None,
        p75=round(pct(prices, 75), 2) if prices else None,
        used_count=len(prices),
        prices=prices,
        raw_count=len(raw),
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
    }

    _cache[cache_key] = {"t": now_ts, "data": result}
    return result


# =========================
# Flask app & routes
# =========================
app = Flask(__name__)


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
