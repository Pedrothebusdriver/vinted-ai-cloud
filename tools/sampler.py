#!/usr/bin/env python3
"""Download sample images from loremflickr, Openverse, or Vinted."""

from __future__ import annotations

import hashlib
import io
import json
import os
import random
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
PI_APP_DIR = REPO_ROOT / "pi-app"
if str(PI_APP_DIR) not in sys.path:
    sys.path.insert(0, str(PI_APP_DIR))

try:
    from app import compliance
except Exception:  # pragma: no cover - fallback when OpenCV/compliance is unavailable
    compliance = None

DEFAULT_BUCKETS = ["jackets", "hoodies", "jeans", "shirts", "shoes"]
raw_buckets = os.environ.get("SAMPLER_BUCKETS")
BUCKETS = [b.strip() for b in raw_buckets.split(",") if b.strip()] if raw_buckets else DEFAULT_BUCKETS
PER_BUCKET = int(os.environ.get("SAMPLER_PER_BUCKET", "10"))
TOTAL_LIMIT = int(os.environ.get("SAMPLER_TOTAL_LIMIT", "50"))
SOURCE = os.environ.get("SAMPLER_SOURCE", "openverse").lower()

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

VINTED_CREDENTIALS_PATH = Path(
    os.environ.get("VINTED_CREDENTIALS_PATH", Path.home() / "secrets" / "vinted.json")
)
VINTED_BASE_FALLBACK = "https://www.vinted.co.uk"
VINTED_UA_LIST = [
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


def safe_name(url: str) -> str:
    n = url.split("/")[-1][:80]
    if not n.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        n += ".jpg"
    return "".join(c if (c.isalnum() or c in "._- ") else "_" for c in n)


def fetch(url: str) -> Optional[bytes]:
    try:
        r = requests.get(url, timeout=20, headers=UA)
        if r.ok and r.content:
            return r.content
    except Exception:
        return None
    return None


def small_hash(im: Image.Image) -> str:
    small = im.resize((48, 48))
    buf = io.BytesIO()
    small.save(buf, format="PNG")
    return hashlib.sha1(buf.getvalue()).hexdigest()


def _load_vinted_config() -> Optional[Dict]:
    if not VINTED_CREDENTIALS_PATH.exists():
        return None
    try:
        return json.loads(VINTED_CREDENTIALS_PATH.read_text())
    except Exception:
        return None


def _normalise_base(region: Optional[str]) -> str:
    if not region:
        return VINTED_BASE_FALLBACK
    if region.startswith("http"):
        return region.rstrip("/")
    trimmed = region.lstrip(".")
    if "." not in trimmed:
        return VINTED_BASE_FALLBACK
    return f"https://www.vinted.{trimmed}"


def _mk_vinted_session(base_url: str, cfg: Optional[Dict]) -> requests.Session:
    headers = {
        "User-Agent": random.choice(VINTED_UA_LIST),
        "Accept": "application/json",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": f"{base_url}/",
        "X-Requested-With": "XMLHttpRequest",
    }
    s = requests.Session()
    s.headers.update(headers)
    token = (cfg or {}).get("access_token") or (cfg or {}).get("token")
    cookie = (cfg or {}).get("cookie")
    if token:
        s.headers["Authorization"] = f"Bearer {token}"
    if cookie:
        s.headers["Cookie"] = cookie
    extra_headers = (cfg or {}).get("headers")
    if isinstance(extra_headers, dict):
        s.headers.update({str(k): str(v) for k, v in extra_headers.items()})
    return s


def _prime_vinted_session(session: requests.Session, base_url: str) -> None:
    try:
        session.get(base_url, timeout=15)
    except Exception:
        pass


def _resolve_vinted_photo_url(
    session: requests.Session, base_url: str, item: Dict
) -> Optional[str]:
    photos = item.get("photos") or []
    if photos:
        url = photos[0].get("url") or (photos[0].get("thumbnails") or [{}])[-1].get("url")
        if url:
            return url
    detail_url = item.get("item_url") or item.get("url")
    if detail_url:
        if detail_url.startswith("/"):
            detail_url = f"{base_url}{detail_url}"
        try:
            resp = session.get(detail_url, timeout=20)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                og = soup.find("meta", attrs={"property": "og:image"})
                if og and og.get("content"):
                    return og["content"]
                img = soup.find("img", src=True)
                if img:
                    return img["src"]
        except Exception:
            return None
    return None


def _fetch_vinted_items(term: str, session: requests.Session, base_url: str, limit: int) -> List[Dict]:
    url = f"{base_url}/api/v2/catalog/items"
    params = {"search_text": term, "per_page": min(limit, 20), "page": 1, "order": "newest_first"}
    try:
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("items") or data.get("data") or []
            if items:
                return items
    except Exception:
        pass

    # HTML fallback for when the JSON endpoint fails or returns nothing.
    try:
        html_resp = session.get(f"{base_url}/catalog", params={"search_text": term}, timeout=20)
        if html_resp.status_code != 200:
            return []
        soup = BeautifulSoup(html_resp.text, "html.parser")
        anchors = soup.select("a[href*='/items/']")[:limit]
        items: List[Dict] = []
        for a in anchors:
            href = a.get("href") or ""
            title = a.get("aria-label") or a.get_text(" ", strip=True) or "Item"
            photo = None
            img = a.find("img")
            if img and img.get("src"):
                photo = [{"url": img.get("src")}]
            items.append(
                {
                    "id": href.rstrip("/").split("/")[-1],
                    "title": title,
                    "item_url": f"{base_url}{href}" if href.startswith("/") else href,
                    "photos": photo or [],
                }
            )
        return items
    except Exception:
        return []


def get_vinted_urls(q: str, limit: int) -> List[str]:
    cfg = _load_vinted_config()
    base_url = _normalise_base((cfg or {}).get("region"))
    session = _mk_vinted_session(base_url, cfg)
    _prime_vinted_session(session, base_url)
    urls: List[str] = []
    try:
        items = _fetch_vinted_items(q, session, base_url, limit * 2)
        for item in items:
            url = _resolve_vinted_photo_url(session, base_url, item)
            if not url:
                continue
            if url not in urls:
                urls.append(url)
            if len(urls) >= limit:
                break
    except Exception as exc:
        print(f"[warn] vinted fetch failed for '{q}': {exc}", file=sys.stderr)
        return []
    return urls


def get_urls(q: str, limit: int) -> List[str]:
    if SOURCE == "lorem":
        return [f"lorem://{q}#{i}" for i in range(limit)]

    if SOURCE == "vinted":
        return get_vinted_urls(q, limit)

    # Default: Openverse
    base = "https://api.openverse.engineering/v1/images"
    params = {"q": q, "page_size": min(limit, 50), "fields": "url"}
    try:
        r = requests.get(base, params=params, timeout=15, headers=UA)
        if r.ok:
            return [x.get("url") for x in r.json().get("results", []) if x.get("url")]
    except Exception:
        pass

    # Fallback: curl (more tolerant of TLS issues in older environments)
    try:
        cmd = [
            "curl",
            "-sL",
            "-H",
            "Accept: application/json",
            f"{base}?{urlencode(params)}",
        ]
        raw = subprocess.check_output(cmd, timeout=20)
        data = json.loads(raw.decode("utf-8"))
        return [x.get("url") for x in data.get("results", []) if x.get("url")]
    except Exception:
        return []


def run() -> None:
    out_root = Path("data/online-samples") / date.today().isoformat()
    out_root.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, object] = {
        "when": datetime.utcnow().isoformat() + "Z",
        "out": str(out_root),
        "results": [],
    }
    total_saved = 0

    for bucket in BUCKETS:
        bdir = out_root / bucket.replace(" ", "_")
        bdir.mkdir(parents=True, exist_ok=True)

        urls = get_urls(bucket, PER_BUCKET * 2)
        seen = set()
        kept = 0
        saved: List[str] = []
        rejected: List[Dict[str, str]] = []

        for u in urls:
            if kept >= PER_BUCKET:
                break
            if TOTAL_LIMIT and total_saved >= TOTAL_LIMIT:
                break

            effective = u
            if u.startswith("lorem://"):
                term = u.split("://", 1)[1].split("#", 1)[0].replace(" ", "+")
                effective = f"https://loremflickr.com/800/800/{term}"

            data = fetch(effective)
            if not data:
                continue

            try:
                im = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                continue

            if min(im.size) < 256:
                continue

            h = small_hash(im)
            if h in seen:
                continue
            seen.add(h)

            fp = bdir / safe_name(effective)
            suffix_idx = 1
            while fp.exists():
                fp = fp.with_name(f"{fp.stem}_{suffix_idx}{fp.suffix}")
                suffix_idx += 1

            im.save(fp, quality=90)
            if compliance:
                ok, reason = compliance.check_image(fp)
                if not ok:
                    fp.unlink(missing_ok=True)
                    rejected.append({"file": str(fp), "reason": reason})
                    continue

            saved.append(str(fp))
            kept += 1
            total_saved += 1

            if TOTAL_LIMIT and total_saved >= TOTAL_LIMIT:
                break

        summary["results"].append(
            {
                "bucket": bucket,
                "fetched": len(urls),
                "kept": kept,
                "saved": saved,
                "rejected": rejected,
            }
        )
        if TOTAL_LIMIT and total_saved >= TOTAL_LIMIT:
            break

    summary["total_saved"] = total_saved
    (out_root / "_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    run()
