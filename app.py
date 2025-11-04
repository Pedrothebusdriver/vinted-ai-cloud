import os
import math
import time
import random
from urllib.parse import urlencode, quote_plus

import requests
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup

# --------- Config ---------
VINTED_BASE = os.getenv("VINTED_BASE", "https://www.vinted.co.uk").rstrip("/")
UA_LIST = [
    # A few realistic desktop/mobile UAs (kept tiny to save memory)
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Mobile Safari/537.36",
]

DEFAULT_TIMEOUT = (5, 15)  # (connect, read) seconds
MAX_ITEMS = 40             # cap to keep memory low
EXAMPLES_LIMIT = 5


# --------- Helpers ---------
def pct(values, p):
    """Simple percentile without numpy."""
    if not values:
        return None
    values = sorted(values)
    k = (len(values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    d0 = values[int(f)] * (c - k)
    d1 = values[int(c)] * (k - f)
    return d0 + d1


def median(values):
    return pct(values, 50)


def mk_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": random.choice(UA_LIST),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def normalize_query(brand, item_type, size, colour):
    parts = []
    for x in (brand, item_type, size, colour):
        if x:
            parts.append(str(x))
    q = " ".join(parts).strip()
    # Light cleanup
    q = " ".join(q.split())
    return q


def parse_price(text):
    """Extract a GBP price float from a bit of text like '£12.50' or '12 GBP'."""
    if not text:
        return None
    t = text.replace(",", "").strip()
    # Common forms
    if "£" in t:
        t = t.split("£", 1)[-1]
    if "GBP" in t.upper():
        t = t.upper().replace("GBP", "").strip()
    # Keep only numbers and dot
    cleaned = []
    dot_seen = False
    for ch in t:
        if ch.isdigit():
            cleaned.append(ch)
        elif ch == "." and not dot_seen:
            cleaned.append(".")
            dot_seen = True
        elif ch in " ":
            cleaned.append(" ")
    t2 = "".join(cleaned).strip()
    # Last token usually the price
    token = t2.split()[-1] if t2 else ""
    try:
        val = float(token)
        # guard against absurd values
        if 0 < val < 10000:
            return val
    except Exception:
        return None
    return None


def uniq(seq):
    seen = set()
    out = []
    for x in seq:
        k = (x.get("url"), x.get("title"), x.get("price_gbp"))
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


# --------- Vinted fetchers ---------
def fetch_vinted_api(query, session):
    """
    Try Vinted's JSON endpoint first. Shape can change; we keep it defensive.
    Returns list of dicts: {'title': str, 'price_gbp': float, 'url': str}
    """
    results = []
    # Candidate endpoints (we try a couple of bases in case of locale)
    api_urls = [
        f"{VINTED_BASE}/api/v2/catalog/items",
        f"{VINTED_BASE}/api/v2/catalog/items.json",
    ]
    params = {
        "search_text": query,
        "per_page": 40,
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
                # Known shapes (defensive):
                title = (
                    it.get("title")
                    or it.get("description")
                    or it.get("brand_title")
                    or "Item"
                )
                # price fields seen historically:
                price_val = (
                    it.get("price") or
                    it.get("price_numeric") or
                    (it.get("price_with_currency", {}).get("amount") if isinstance(it.get("price_with_currency"), dict) else None)
                )
                if isinstance(price_val, str):
                    price_val = parse_price(price_val)
                elif isinstance(price_val, (int, float)):
                    price_val = float(price_val)
                else:
                    price_val = None

                web_url = it.get("url") or it.get("path")
                if web_url and web_url.startswith("/"):
                    web_url = VINTED_BASE + web_url
                if not web_url:
                    # fallback: sometimes 'id' present
                    iid = it.get("id")
                    if iid:
                        web_url = f"{VINTED_BASE}/items/{iid}"

                if price_val:
                    results.append({
                        "title": str(title)[:120],
                        "price_gbp": price_val,
                        "url": web_url or VINTED_BASE
                    })
            if results:
                break
        except Exception:
            continue
    return results


def fetch_vinted_html(query, session):
    """
    Fallback: parse HTML search page.
    Returns list of dicts: {'title': str, 'price_gbp': float, 'url': str}
    """
    results = []
    # Example search: /catalog?search_text=...&order=newest_first
    params = {"search_text": query, "order": "newest_first"}
    url = f"{VINTED_BASE}/catalog"
    try:
        r = session.get(url, params=params, timeout=DEFAULT_TIMEOUT)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "lxml")

        # Look for item cards. Vinted markup changes; we collect broadly.
        anchors = soup.select("a[href*='/items/']")
        for a in anchors[:MAX_ITEMS]:
            href = a.get("href")
            if not href:
                continue
            url = href if href.startswith("http") else (VINTED_BASE + href)

            # Try to find price near the anchor
            price_text = None
            # Common patterns: elements with text containing '£'
            # Check the link text and nearby siblings
            texts = []
            texts.append(a.get_text(" ", strip=True))
            parent = a.parent
            if parent:
                texts.append(parent.get_text(" ", strip=True))
                if parent.parent:
                    texts.append(parent.parent.get_text(" ", strip=True))
            for t in texts:
                if "£" in t or "GBP" in t.upper():
                    price_text = t
                    break
            price = parse_price(price_text)

            # Title heuristic: anchor text or aria-label
            title = a.get("aria-label") or a.get_text(" ", strip=True) or "Item"
            if price:
                results.append({
                    "title": title[:120],
                    "price_gbp": price,
                    "url": url
                })
    except Exception:
        return results
    return results


def get_comps(brand, item_type, size, colour):
    """
    Main comps fetcher: builds a query string and tries API, then HTML.
    Returns dict with median/p25/p75 and examples.
    """
    q = normalize_query(brand, item_type, size, colour)
    sess = mk_session()

    # Try API then fallback HTML
    items = fetch_vinted_api(q, sess)
    if not items:
        time.sleep(0.4)  # small jitter
        items = fetch_vinted_html(q, sess)

    # Deduplicate and trim
    items = uniq(items)[:MAX_ITEMS]
    prices = [x["price_gbp"] for x in items if x.get("price_gbp")]

    if not prices:
        return {
            "query": q,
            "count": 0,
            "median_price_gbp": None,
            "p25_gbp": None,
            "p75_gbp": None,
            "examples": [],
        }

    ex = items[:EXAMPLES_LIMIT]
    return {
        "query": q,
        "count": len(prices),
        "median_price_gbp": round(median(prices), 2) if prices else None,
        "p25_gbp": round(pct(prices, 25), 2) if prices else None,
        "p75_gbp": round(pct(prices, 75), 2) if prices else None,
        "examples": [
            {"title": e["title"], "price_gbp": round(e["price_gbp"], 2), "url": e["url"]}
            for e in ex
        ],
    }


# --------- Flask App ---------
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


# Backwards-compat fallback
@app.get("/price")
def price():
    return api_price()


# Optional: local debug run (Render uses gunicorn; this block is ignored there)
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5055"))
    app.run(host="0.0.0.0", port=port, debug=False)
