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
