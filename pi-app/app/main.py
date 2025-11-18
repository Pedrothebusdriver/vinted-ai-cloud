import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import re
import shutil
import subprocess
import time
import sqlite3
from collections import defaultdict, deque
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

import httpx
import structlog
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError
from prometheus_client import Counter
from prometheus_fastapi_instrumentator import Instrumentator

from app import compliance, events
from app.api.schemas import DraftResponseSchema, DraftSummarySchema, DraftUpdatePayload
from app.classifier import dominant_colour, item_type_from_name
from app.core.ingest import DraftRejected, IngestPaths, IngestService
from app.core.models import Draft, PriceEstimate
from app.core.pricing import PricingService
from app.db import connect, init_db, now
from app.export import build_listing_pack
from app.ocr import OCR

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger("vinted-pi")
ITEMS_PROCESSED = Counter("pi_items_processed_total", "Items processed by the Pi app", ["status"])
LEARNING_POSTS = Counter("pi_learning_posts_total", "Learning snapshots posted")
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_respect_env_var=True,
)
ITEMS_PROCESSED.labels(status="ok")
ITEMS_PROCESSED.labels(status="rejected")

# ---------- Env / paths ----------
load_dotenv()


def _detect_version() -> str:
    env_version = os.getenv("APP_VERSION")
    if env_version:
        return env_version
    try:
        repo_root = Path(__file__).resolve().parents[2]
    except Exception:
        repo_root = Path(".").resolve()
    try:
        return (
            subprocess.check_output(
                ["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "dev"
WEBHOOK = os.getenv('DISCORD_WEBHOOK_URL', '')
WEBHOOK_GENERAL = os.getenv('DISCORD_WEBHOOK_GENERAL', WEBHOOK)
WEBHOOK_DRAFTS = os.getenv('DISCORD_WEBHOOK_DRAFTS', WEBHOOK)
ALERT_WEBHOOK = os.getenv('DISCORD_WEBHOOK_ALERTS', '')
COMPS_BASE = os.getenv('COMPS_BASE_URL', '')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', 'http://localhost:8080').rstrip('/')
_upload_key_raw = os.getenv('UPLOAD_API_KEYS') or os.getenv('UPLOAD_API_KEY', '')
UPLOAD_API_KEYS = {token.strip() for token in re.split(r'[,\s]+', _upload_key_raw) if token.strip()}
try:
    UPLOAD_RATE_LIMIT = max(0, int(os.getenv('UPLOAD_RATE_LIMIT', '20')))
except ValueError:
    UPLOAD_RATE_LIMIT = 20
try:
    UPLOAD_RATE_WINDOW_SECONDS = max(1, int(os.getenv('UPLOAD_RATE_WINDOW_SECONDS', '60')))
except ValueError:
    UPLOAD_RATE_WINDOW_SECONDS = 60

_upload_rate_hits: Dict[str, deque] = defaultdict(deque)
_upload_rate_lock = Lock()

BASE = Path('.')
INP = BASE / 'input_images'
OUT = BASE / 'converted_images'
BAK = BASE / 'backups'
THUMBS = BASE / 'static' / 'thumbs'
VAR_DIR = BASE / 'var'
INFER_TMP = VAR_DIR / 'infer'
SAMPLES = BASE / 'data' / 'online-samples'
EVALS = BASE / 'data' / 'evals'
INGEST_META = BASE / 'data' / 'ingest-meta'
for p in (INP, OUT, BAK, THUMBS, VAR_DIR, INFER_TMP, SAMPLES, EVALS, INGEST_META):
    p.mkdir(parents=True, exist_ok=True)

# Limit heavy conversions on small Pi
CONVERT_SEM = asyncio.Semaphore(1)
APP_VERSION = _detect_version()
STARTED_AT = time.time()

# ---------- FastAPI ----------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount('/static', StaticFiles(directory='static'), name='static')
app.mount('/samples', StaticFiles(directory=str(SAMPLES)), name='samples')
tmpl = Jinja2Templates(directory='templates')
ocr = OCR()
if UPLOAD_API_KEYS:
    log.info("upload_auth_enabled", key_count=len(UPLOAD_API_KEYS))
if UPLOAD_RATE_LIMIT:
    log.info(
        "upload_rate_limit_enabled",
        limit=UPLOAD_RATE_LIMIT,
        window_seconds=UPLOAD_RATE_WINDOW_SECONDS,
    )

# ---------- Auto-init DB on startup ----------
@app.on_event("startup")
def _ensure_db_ready():
    try:
        from app import db as d
        Path(d.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
        init_db()
        # Learning tables (future-proof outbox)
        with connect() as c:
            c.execute('''create table if not exists learned_labels (
                label_hash text primary key,
                brand text,
                size text,
                seen_text text,
                created_at text
            )''')
            c.execute('''create table if not exists learning_events (
                id integer primary key autoincrement,
                kind text,
                payload_json text,
                created_at text,
                synced_at text
            )''')
            c.commit()
        log.info("DB ready at %s", d.DB_PATH)
        try:
            instrumentator.instrument(app).expose(app)
            log.info("metrics_endpoint_ready")
        except Exception as exc:
            log.warning("metrics_setup_failed", error=str(exc))
    except Exception as e:
        log.warning("DB init warning: %s", e)

# ---------- Brand lexicon & helpers ----------
# If app/data/brands.json exists use it, else fallback to this seed list
_DEFAULT_BRANDS = [
    "Nike",
    "Adidas",
    "Puma",
    "Reebok",
    "New Balance",
    "Asics",
    "Under Armour",
    "The North Face",
    "TNF",
    "Columbia",
    "Patagonia",
    "Berghaus",
    "Arc'teryx",
    "Helly Hansen",
    "Salomon",
    "Hoka",
    "Vans",
    "Converse",
    "Levi's",
    "Lee",
    "Wrangler",
    "Carhartt",
    "Dickies",
    "G-Star",
    "Diesel",
    "Zara",
    "H&M",
    "Uniqlo",
    "Next",
    "ASOS",
    "Boohoo",
    "Bershka",
    "Pull & Bear",
    "Massimo Dutti",
    "COS",
    "Monki",
    "Topshop",
    "River Island",
    "AllSaints",
    "Ralph Lauren",
    "Tommy Hilfiger",
    "Lacoste",
    "Calvin Klein",
    "Guess",
    "Superdry",
    "Hollister",
    "Abercrombie",
    "Stone Island",
    "CP Company",
    "Barbour",
    "Belstaff",
    "Fred Perry",
    "Ted Baker",
    "Boss",
    "Michael Kors",
    "Kate Spade",
    "Coach",
    "Balenciaga",
    "Gucci",
    "Prada",
    "Louis Vuitton",
    "Chanel",
    "White Fox",
    "Peacocks",
    "New Look",
]

try:
    BRANDS = json.loads((BASE/"app"/"data"/"brands.json").read_text())
    if not isinstance(BRANDS, list):
        BRANDS = _DEFAULT_BRANDS
except Exception:
    BRANDS = _DEFAULT_BRANDS

try:
    from rapidfuzz import fuzz, process
except Exception:
    process = None
    fuzz = None

_BRAND_MIN_SCORE_HIGH = 90
_BRAND_MIN_SCORE_MED = 80

SIZE_PATTERNS = [
    (re.compile(r"\b(XXS|XS|S|M|L|XL|XXL|XXXL)\b", re.I), lambda m: m.group(1).upper(), 'High'),
    (re.compile(r"\bUK\s?(\d{1,2})\b", re.I), lambda m: f"UK {m.group(1)}", 'High'),
    (re.compile(r"\bEU\s?(\d{2})\b", re.I), lambda m: f"EU {m.group(1)}", 'High'),
    (re.compile(r"\bUS\s?(\d{1,2})\b", re.I), lambda m: f"US {m.group(1)}", 'High'),
    (
        re.compile(r"\bW(\d{2})\s*[xX ]\s*L?(\d{2})\b", re.I),
        lambda m: f"W{m.group(1)} L{m.group(2)}",
        'High',
    ),
]

def detect_brand_size(label_text: str) -> Tuple[Optional[str], str, Optional[str], str]:
    """Return (brand, brand_conf, size, size_conf)."""
    brand = None
    bconf = 'Low'
    size = None
    sconf = 'Low'

    nt = _normalize_text(label_text)

    if process:
        match = process.extractOne(nt, BRANDS, scorer=fuzz.token_set_ratio)
        if match:
            name, score = match[0], match[1]
            if score >= _BRAND_MIN_SCORE_HIGH:
                brand, bconf = name, 'High'
            elif score >= _BRAND_MIN_SCORE_MED:
                brand, bconf = name, 'Medium'

    for rx, fn, conf in SIZE_PATTERNS:
        m = rx.search(label_text)
        if m:
            size = fn(m)
            sconf = conf
            break

    return brand, bconf, size, sconf

# ---------- OCR helpers ----------
def _preprocess_for_ocr(img_path: Path) -> Path:
    """Lightweight label boost: grayscale + autocontrast + threshold."""
    try:
        from PIL import ImageEnhance, ImageFilter, ImageOps
        im = Image.open(img_path)
        im = im.convert('L')  # grayscale
        im = ImageOps.autocontrast(im)
        im = ImageEnhance.Contrast(im).enhance(1.6)
        im = im.filter(ImageFilter.MedianFilter(size=3))
        # simple threshold
        im = im.point(lambda p: 255 if p > 160 else 0)
        out = img_path.with_suffix('.ocr.jpg')
        im.save(out, quality=85)
        return out
    except Exception as e:
        log.warning("preprocess failed for %s: %s", img_path, e)
        return img_path

def _load_ingest_meta(item_id: int) -> Dict[str, Any]:
    path = INGEST_META / f'item-{item_id}.json'
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception as exc:
            log.warning("ingest meta parse failed for item %s: %s", item_id, exc)
    return {}

def _write_ingest_meta(item_id: int, payload: Dict[str, Any]) -> None:
    meta_path = INGEST_META / f'item-{item_id}.json'
    meta_path.write_text(json.dumps(payload, indent=2))

def _lookup_learned_label(label_hash: str) -> Optional[Tuple[Optional[str], Optional[str]]]:
    with connect() as c:
        row = c.execute(
            'select brand, size from learned_labels where label_hash=?',
            (label_hash,),
        ).fetchone()
    if row:
        return row['brand'], row['size']
    return None

# ---------- Image conversion (DNG/HEIC/RAW -> JPEG) ----------
def _run_im_cmd(args: List[str]) -> bool:
    for cmd in ('magick', 'convert'):
        try:
            subprocess.run([cmd] + args, check=True, timeout=20,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    return False

def _extract_dng_preview(src_path: Path, dst_path: Path) -> bool:
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        ["exiftool", "-b", "-PreviewImage", str(src_path)],
        ["exiftool", "-b", "-JpgFromRaw", str(src_path)],
        ["exiftool", "-b", "-ThumbnailImage", str(src_path)],
    ]
    for cmd in candidates:
        try:
            data = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=15)
            if data and len(data) > 10_000:
                with open(dst_path, "wb") as f:
                    f.write(data)
                return True
        except Exception:
            continue
    return False

def to_jpeg(src_path: Path, dst_path: Path) -> bool:
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        ext = src_path.suffix.lower()

        if ext in {'.jpg', '.jpeg', '.png'}:
            img = Image.open(src_path).convert('RGB')
            img.thumbnail((1600, 1600))
            img.save(dst_path, quality=85)
            return True

        if ext == '.dng':
            if _extract_dng_preview(src_path, dst_path):
                return True
            if _run_im_cmd([
                str(src_path),
                '-auto-orient',
                '-resize',
                '1600x1600>',
                '-quality',
                '85',
                str(dst_path),
            ]):
                return True
            img = Image.open(src_path).convert('RGB')
            img.thumbnail((1600, 1600))
            img.save(dst_path, quality=85)
            return True

        if _run_im_cmd([
            str(src_path),
            '-auto-orient',
            '-resize',
            '1600x1600>',
            '-quality',
            '85',
            str(dst_path),
        ]):
            return True

        img = Image.open(src_path).convert('RGB')
        img.thumbnail((1600, 1600))
        img.save(dst_path, quality=85)
        return True

    except (UnidentifiedImageError, OSError, subprocess.TimeoutExpired) as e:
        log.warning("to_jpeg failed for %s: %s", src_path, e)
        return False

def make_thumb(jpeg_path: Path, thumb_path: Path) -> None:
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    if not _run_im_cmd([str(jpeg_path), '-thumbnail', '128x128', str(thumb_path)]):
        try:
            img = Image.open(jpeg_path).copy()
            img.thumbnail((128, 128))
            img.save(thumb_path, quality=70)
        except Exception as e:
            log.warning("thumb failed for %s: %s", jpeg_path, e)

# ---------- Brand & size detection ----------
def _normalize_text(t: str) -> str:
    t = re.sub(r"[^a-z0-9\s]", " ", t.lower())
    t = re.sub(r"\s+", " ", t).strip()
    return t

def _label_hash(t: str) -> str:
    return hashlib.sha1(_normalize_text(t).encode('utf-8')).hexdigest()

SAMPLE_IMG_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}

def _sample_relative_url(path_like) -> Optional[str]:
    if not path_like:
        return None
    p = Path(path_like)
    if not p.is_absolute():
        p = (BASE / p).resolve()
    try:
        rel = p.resolve().relative_to(SAMPLES.resolve())
        return f"/samples/{rel.as_posix()}"
    except Exception:
        return None

def _collect_sample_sets(max_days: int = 4, max_buckets: int = 6, max_images: int = 6):
    if not SAMPLES.exists():
        return []
    days = sorted([d for d in SAMPLES.iterdir() if d.is_dir()], reverse=True)
    output = []
    for day in days[:max_days]:
        bucket_rows = []
        buckets = sorted([b for b in day.iterdir() if b.is_dir()])
        for bucket in buckets[:max_buckets]:
            images = sorted(
                [
                    p
                    for p in bucket.glob("*")
                    if p.is_file() and p.suffix.lower() in SAMPLE_IMG_EXTS
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not images:
                continue
            bucket_rows.append({
                "name": bucket.name,
                "count": len(images),
                "folder_url": f"/samples/{day.name}/{bucket.name}",
                "images": [
                    u
                    for u in (_sample_relative_url(img) for img in images[:max_images])
                    if u
                ],
                "local_paths": [str(img) for img in images[:max_images]],
            })
        if bucket_rows:
            output.append({"date": day.name, "buckets": bucket_rows})
    return output

def _pick_sample_images(limit: int = 3) -> List[Path]:
    picks: List[Path] = []
    if not SAMPLES.exists():
        return picks
    days = sorted([d for d in SAMPLES.iterdir() if d.is_dir()], reverse=True)
    for day in days:
        buckets = sorted([b for b in day.iterdir() if b.is_dir()])
        for bucket in buckets:
            images = sorted(
                [
                    p
                    for p in bucket.glob("*")
                    if p.is_file() and p.suffix.lower() in SAMPLE_IMG_EXTS
                ],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for img in images:
                picks.append(img)
                if len(picks) >= limit:
                    return picks
    return picks

ALLOWED_CONDITIONS = [
    "New with tags",
    "New without tags",
    "Very good",
    "Good",
    "Fair",
]
PRICE_MIN_PENCE = int(os.getenv("VINTED_PRICE_MIN_PENCE", "50"))   # £0.50
PRICE_MAX_PENCE = int(os.getenv("VINTED_PRICE_MAX_PENCE", "50000"))  # £500

def _make_listing_title(
    brand: Optional[str],
    item_type: str,
    colour: str,
    size: Optional[str],
) -> str:
    parts = []
    if brand:
        parts.append(_sanitize_attr(brand, 30).title())
    if colour and colour.lower() not in {"unknown", "mixed"}:
        parts.append(_sanitize_attr(colour, 20).title())
    if item_type:
        parts.append(_sanitize_attr(item_type, 30).title())
    if size:
        parts.append(f"Size { _sanitize_attr(size, 12).upper() }")
    title = " ".join([p for p in parts if p]).strip() or "Clothing Item"
    return title[:80]

pricing_service = PricingService(COMPS_BASE, PRICE_MIN_PENCE, PRICE_MAX_PENCE)
ingest_service = IngestService(
    ocr=ocr,
    pricing_service=pricing_service,
    paths=IngestPaths(
        converted_root=OUT,
        thumbs_root=THUMBS,
        placeholder_thumb=Path('static/no-thumb.png'),
    ),
    to_jpeg=to_jpeg,
    make_thumb=make_thumb,
    preprocess_for_ocr=_preprocess_for_ocr,
    detect_brand_size=detect_brand_size,
    label_hash_fn=_label_hash,
    dominant_colour=dominant_colour,
    item_type_from_name=item_type_from_name,
    make_listing_title=_make_listing_title,
    learned_lookup=_lookup_learned_label,
    convert_semaphore=CONVERT_SEM,
)

def _sanitize_attr(value: str, max_len: int = 60) -> str:
    v = (value or "").strip()
    if len(v) > max_len:
        v = v[:max_len].rstrip()
    return v

def _normalize_condition(value: str) -> str:
    v = (value or "").strip().lower()
    for opt in ALLOWED_CONDITIONS:
        if v == opt.lower():
            return opt
    return ""

def _price_to_pence(price: str) -> Optional[int]:
    if not price:
        return None
    cleaned = price.replace("£", "").strip()
    cleaned = cleaned.replace(",", "")
    try:
        pounds = round(float(cleaned), 2)
    except (TypeError, ValueError):
        return None
    if pounds <= 0:
        return None
    return int(pounds * 100)

def _clamp_price(pence: Optional[int]) -> Optional[int]:
    if pence is None:
        return None
    return max(PRICE_MIN_PENCE, min(PRICE_MAX_PENCE, pence))

def _gbp_to_pence(value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    return int(round(value * 100))

def _pence_to_gbp(value: Optional[int]) -> Optional[float]:
    if value is None:
        return None
    return round(value / 100.0, 2)

def _cleanup_temp_files(*paths: Optional[Path]) -> None:
    for p in paths:
        if isinstance(p, Path):
            with suppress(FileNotFoundError):
                p.unlink()

def _client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"

def _extract_upload_token(request: Request) -> Optional[str]:
    header = request.headers.get('x-upload-key') or request.headers.get('authorization') or request.query_params.get('upload_key')
    if not header:
        return None
    if header.lower().startswith('bearer '):
        header = header.split(' ', 1)[1]
    return header.strip() or None

def _require_upload_auth(request: Request) -> None:
    if not UPLOAD_API_KEYS:
        return
    token = _extract_upload_token(request)
    if not token or token not in UPLOAD_API_KEYS:
        log.warning("upload_auth_failed", remote=_client_ip(request))
        raise HTTPException(status_code=401, detail="Upload authentication required.")

def _enforce_upload_rate_limit(request: Request) -> None:
    if not UPLOAD_RATE_LIMIT:
        return
    now_ts = time.monotonic()
    window_start = now_ts - UPLOAD_RATE_WINDOW_SECONDS
    key = _client_ip(request)
    with _upload_rate_lock:
        hits = _upload_rate_hits[key]
        while hits and hits[0] < window_start:
            hits.popleft()
        if len(hits) >= UPLOAD_RATE_LIMIT:
            log.warning("upload_rate_limited", remote=key)
            raise HTTPException(status_code=429, detail="Upload rate limit exceeded. Try again shortly.")
        hits.append(now_ts)

def _format_epoch(ts: Optional[str]) -> str:
    if ts in (None, '', 0):
        return ''
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(ts)

def _load_learned_labels(limit: int = 25):
    rows = []
    with connect() as c:
        query = (
            "select label_hash, brand, size, seen_text, created_at "
            "from learned_labels "
            "order by CAST(coalesce(created_at,'0') AS INTEGER) desc "
            f"limit {int(limit)}"
        )
        for r in c.execute(query):
            rows.append({
                "hash": r['label_hash'],
                "brand": r['brand'] or '',
                "size": r['size'] or '',
                "text": (r['seen_text'] or '')[:200],
                "created_at": _format_epoch(r['created_at']),
            })
    return rows

def _latest_eval_snapshot(max_examples: int = 6):
    if not EVALS.exists():
        return None
    days = sorted([d for d in EVALS.iterdir() if d.is_dir()], reverse=True)
    lines = []
    day_name = ""
    for day in days:
        files = sorted(day.glob("*.jsonl"), reverse=True)
        for fpath in files:
            try:
                with open(fpath, 'r', encoding='utf-8') as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            lines.append(json.loads(line))
                        except Exception:
                            continue
            except FileNotFoundError:
                continue
        if lines:
            day_name = day.name
            break
    if not lines:
        return None

    total = len(lines)
    correct = sum(1 for x in lines if x.get("correct"))
    buckets = defaultdict(lambda: {"n": 0, "ok": 0})
    for rec in lines:
        bucket = rec.get("bucket") or "(unknown)"
        buckets[bucket]["n"] += 1
        if rec.get("correct"):
            buckets[bucket]["ok"] += 1

    bucket_rows = []
    for name, stats in sorted(buckets.items(), key=lambda kv: (-kv[1]["n"], kv[0]))[:6]:
        acc = (100.0 * stats["ok"] / stats["n"]) if stats["n"] else 0.0
        bucket_rows.append({"name": name, "n": stats["n"], "acc": round(acc, 1)})

    hard = []
    for rec in lines:
        if rec.get("correct"):
            continue
        img_url = _sample_relative_url(rec.get("file"))
        hard.append({
            "bucket": rec.get("bucket") or "(unknown)",
            "pred": rec.get("pred_category") or "—",
            "tags": ", ".join(rec.get("pred_tags") or []) or "—",
            "price": rec.get("pred_price"),
            "image": img_url,
        })
        if len(hard) >= max_examples:
            break

    return {
        "date": day_name,
        "accuracy": round((100.0 * correct / total), 1) if total else 0.0,
        "total": total,
        "bucket_rows": bucket_rows,
        "hard_examples": hard,
    }

async def _reject_item(item_id: int, reasons: List[str]) -> None:
    reason_text = "; ".join(reasons) or "non_compliant"
    log.warning("Item %s rejected: %s", item_id, reason_text)
    ITEMS_PROCESSED.labels(status="rejected").inc()
    events.record_event("item_rejected", {"item_id": item_id, "reasons": reasons})
    if ALERT_WEBHOOK:
        try:
            async with httpx.AsyncClient(timeout=8) as cli:
                await cli.post(ALERT_WEBHOOK, json={"content": f"🚫 Draft #{item_id} rejected: {reason_text[:1800]}"} )
        except Exception as exc:
            log.warning("Alert webhook failed: %s", exc)
    with connect() as c:
        for table in ('photos','attributes','drafts','prices','comps'):
            c.execute(f'delete from {table} where item_id=?', (item_id,))
        c.execute('update items set status=? where id=?', ('rejected', item_id))
        c.commit()
    for folder in (INP / f'item-{item_id}', OUT / f'item-{item_id}', BAK / f'item-{item_id}'):
        shutil.rmtree(folder, ignore_errors=True)

def _create_item(status: str = "draft") -> int:
    with connect() as c:
        c.execute('insert into items(status,created_at,updated_at) values(?,?,?)', (status, now(), now()))
        item_id = c.execute('select last_insert_rowid()').fetchone()[0]
        c.commit()
    return int(item_id)

async def _save_upload_files(item_id: int, files: List[UploadFile]) -> List[Path]:
    item_dir = INP / f'item-{item_id}'
    bak_dir  = BAK / f'item-{item_id}'
    for p in (item_dir, bak_dir):
        p.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []
    for f in files:
        dest = item_dir / f.filename
        with open(dest, 'wb') as w:
            while True:
                chunk = await f.read(1024*1024)
                if not chunk:
                    break
                w.write(chunk)
        shutil.copyfile(dest, bak_dir / f.filename)
        saved.append(dest)
    return saved

async def _store_ingest_result(item_id: int, draft: Draft, *, started_at: float) -> None:
    brand_conf = draft.metadata.get("brand_confidence", "Auto")
    size_conf = draft.metadata.get("size_confidence", "Auto")
    item_conf = draft.metadata.get("item_confidence", "Auto")
    label_text = draft.label_text or ""
    colour = draft.colour or "Unknown"
    item_type = draft.metadata.get("item_type") or (draft.category_name or "clothing")

    price_low = _gbp_to_pence(draft.price.low)
    price_mid = _gbp_to_pence(draft.price.mid)
    price_high = _gbp_to_pence(draft.price.high)
    with connect() as c:
        ts = now()
        c.execute(
            'insert or ignore into drafts(item_id, created_at, updated_at, status) values (?,?,?,?)',
            (item_id, ts, ts, draft.status or "draft"),
        )
        c.execute('update items set status=?, updated_at=? where id=?', (draft.status or "draft", ts, item_id))
        for idx, photo in enumerate(draft.photos):
            c.execute(
                'insert into photos(item_id, original_path, optimised_path, width, height, is_label, draft_id, file_path, position) values (?,?,?,?,?,?,?,?,?)',
                (
                    item_id,
                    photo.original_path or "",
                    photo.optimised_path or photo.path,
                    0,
                    0,
                    0,
                    item_id,
                    photo.optimised_path or photo.path or "",
                    idx,
                ),
            )
        c.execute(
            '''
            update drafts
            set title=?,
                description=?,
                brand=?,
                size=?,
                colour=?,
                category_id=?,
                category_name=?,
                condition=?,
                status=?,
                price_low_pence=?,
                price_mid_pence=?,
                price_high_pence=?,
                updated_at=?
            where item_id=?
            ''',
            (
                draft.title or "",
                draft.description or "",
                draft.brand or "",
                draft.size or "",
                draft.colour or "",
                draft.category_id,
                draft.category_name,
                draft.condition or "Good",
                draft.status or "draft",
                price_low,
                price_mid,
                price_high,
                ts,
                item_id,
            ),
        )
        attr_rows = [
            ("brand", draft.brand or "", brand_conf),
            ("size", draft.size or "", size_conf),
            ("item_type", item_type, item_conf),
            ("colour", colour, "Medium"),
            ("condition", draft.condition or "Good", "Auto"),
            ("label_text", label_text, "Auto"),
        ]
        if draft.category_id:
            attr_rows.append(("category_id", draft.category_id, "Auto"))
        if draft.category_name:
            attr_rows.append(("category_name", draft.category_name, "Auto"))
        for field, value, confidence in attr_rows:
                c.execute(
                    'insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)',
                    (item_id, field, value or "", confidence),
                )
        rec = _gbp_to_pence(draft.price.mid)
        if draft.price.has_prices and rec is not None:
            p25 = _gbp_to_pence(draft.price.low)
            p75 = _gbp_to_pence(draft.price.high)
            c.execute(
                'insert or replace into prices(item_id, recommended_pence, p25_pence, p75_pence, checked_at) values (?,?,?,?,?)',
                (item_id, rec, p25, p75, now()),
            )
        c.commit()

    if WEBHOOK_DRAFTS:
        try:
            first_photo = draft.photos[0] if draft.photos else None
            thumb_path = None
            if first_photo:
                thumb_path = THUMBS / f"{Path((first_photo.optimised_path or first_photo.path)).stem}.jpg"
            pieces = [
                f"Brand: {draft.brand or '—'} ({brand_conf})",
                f"Size: {draft.size or '—'} ({size_conf})",
                f"Colour: {colour}",
                f"Item: {item_type} ({item_conf})",
            ]
            draft_url = f"{PUBLIC_BASE_URL}/draft/{item_id}"
            content = f"🧵 Draft #{item_id}\n" + "\n".join(pieces) + f"\n{draft_url}"
            files = None
            if thumb_path and thumb_path.exists():
                files = {'file': (thumb_path.name, thumb_path.read_bytes(), 'image/jpeg')}
            async with httpx.AsyncClient(timeout=10) as cli:
                await cli.post(
                    WEBHOOK_DRAFTS,
                    data={"content": content[:1900]},
                    files=files,
                )
        except Exception as e:
            log.warning("draft_webhook_failed", error=str(e))

    duration = round(time.time() - started_at, 2)
    log.info("item_processed", item_id=item_id, seconds=duration)
    ITEMS_PROCESSED.labels(status="ok").inc()
    events.record_event("item_processed", {
        "item_id": item_id,
        "brand": draft.brand,
        "size": draft.size,
        "item_type": item_type,
        "colour": colour,
        "seconds": duration,
    })


def _fetch_photos(conn, draft_id: int, limit: Optional[int] = None) -> List[sqlite3.Row]:
    sql = (
        "select id, original_path, optimised_path, file_path, position "
        "from photos where coalesce(draft_id, item_id)=? "
        "order by position asc, id asc"
    )
    params: List[Any] = [draft_id]
    if limit:
        sql += " limit ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _photo_thumbnail(path_value: Optional[str]) -> Optional[str]:
    if not path_value:
        return None
    path = Path(path_value)
    return f"/static/thumbs/{path.stem}.jpg"


def _serialize_photo_row(row: sqlite3.Row) -> Dict[str, Any]:
    file_path = row["file_path"] or row["optimised_path"] or row["original_path"]
    thumb = _photo_thumbnail(row["optimised_path"])
    return {
        "id": row["id"],
        "original_path": row["original_path"],
        "optimised_path": row["optimised_path"],
        "file_path": file_path,
        "url": thumb or file_path,
        "position": row["position"],
    }


def _serialize_draft_row(row: sqlite3.Row, photos: List[sqlite3.Row], include_photos: bool = True) -> Dict[str, Any]:
    photo_payloads = [_serialize_photo_row(photo) for photo in photos]
    price_low = _pence_to_gbp(row["price_low_pence"])
    price_mid = _pence_to_gbp(row["price_mid_pence"]) or _pence_to_gbp(row["price_pence"])
    price_high = _pence_to_gbp(row["price_high_pence"])
    selected_price = _pence_to_gbp(row["selected_price_pence"] or row["price_pence"])
    payload = {
        "id": row["item_id"],
        "title": row["title"] or f"Draft #{row['item_id']}",
        "description": row["description"],
        "status": row["status"] or "draft",
        "brand": row["brand"],
        "size": row["size"],
        "colour": row["colour"],
        "category_id": row["category_id"],
        "category_name": row["category_name"],
        "condition": row["condition"],
        "price_low": price_low,
        "price_mid": price_mid,
        "price_high": price_high,
        "selected_price": selected_price,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "thumbnail_url": photo_payloads[0]["url"] if photo_payloads else None,
        "photos": photo_payloads if include_photos else [],
    }
    payload["prices"] = {
        "low": price_low,
        "mid": price_mid,
        "high": price_high,
        "selected": selected_price,
    }
    payload["attributes"] = {
        "brand": {"value": row["brand"]},
        "size": {"value": row["size"]},
        "colour": {"value": row["colour"]},
        "status": {"value": row["status"] or "draft"},
        "updated_at": payload["updated_at"],
    }
    return payload


def _load_draft_payload(draft_id: int, *, include_photos: bool = True) -> Optional[Dict[str, Any]]:
    with connect() as c:
        row = c.execute('select * from drafts where item_id=?', (draft_id,)).fetchone()
        if not row:
            return None
        photos = _fetch_photos(c, draft_id, None if include_photos else 1)
        return _serialize_draft_row(row, photos, include_photos)


# ---------- Background job to process one item ----------
async def _process_item(item_id: int, filepaths: List[Path]) -> None:
    start = time.time()
    meta = _load_ingest_meta(item_id)
    try:
        draft = await ingest_service.build_draft(
            item_id=item_id,
            filepaths=filepaths,
            metadata=meta,
        )
    except DraftRejected as exc:
        await _reject_item(item_id, list(exc.reasons))
        return

    await _store_ingest_result(item_id, draft, started_at=start)

# ---------- Routes ----------
@app.get('/health')
def health():
    return {
        "status": "ok",
        "version": APP_VERSION,
        "uptime_seconds": round(time.time() - STARTED_AT, 2),
    }

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return tmpl.TemplateResponse('index.html', {'request': request})

@app.get('/learning', response_class=HTMLResponse)
def learning_dashboard(request: Request):
    samples = _collect_sample_sets()
    eval_snapshot = _latest_eval_snapshot()
    learned = _load_learned_labels()
    return tmpl.TemplateResponse('learning.html', {
        'request': request,
        'sample_sets': samples,
        'eval_snapshot': eval_snapshot,
        'learned_labels': learned,
        'webhook_enabled': bool(WEBHOOK_GENERAL),
    })

@app.post('/api/learning/notify')
async def post_learning_snapshot():
    if not WEBHOOK_GENERAL:
        raise HTTPException(status_code=400, detail="DISCORD_WEBHOOK_GENERAL not configured.")

    eval_snapshot = _latest_eval_snapshot()
    learned = _load_learned_labels(limit=5)
    samples = _collect_sample_sets(max_days=1, max_buckets=3, max_images=3)

    lines = ["Learning snapshot"]
    if eval_snapshot:
        lines.append(f"Eval {eval_snapshot.get('date','?')}: {eval_snapshot.get('accuracy',0)}% over {eval_snapshot.get('total',0)} samples.")
        bucket_bits = [
            f"{row['name']} {row['acc']}% ({row['n']})"
            for row in (eval_snapshot.get('bucket_rows') or [])[:3]
        ]
        if bucket_bits:
            lines.append("Buckets: " + ", ".join(bucket_bits))
    if samples:
        day = samples[0]
        bucket_summaries = [f"{b['name']} ({b['count']})" for b in day.get('buckets', [])[:3]]
        lines.append(f"Sampler {day.get('date')}: " + ", ".join(bucket_summaries))
    if learned:
        lbl_bits = [f"{row['brand'] or '—'} / {row['size'] or '—'}" for row in learned[:3]]
        lines.append("Recent labels: " + ", ".join(lbl_bits))

    content = "\n".join(lines)
    if len(content) > 1900:
        content = content[:1900] + "…"

    attachments = []
    for path in _pick_sample_images(limit=3):
        try:
            if path.stat().st_size > 8 * 1024 * 1024:
                continue
            data = path.read_bytes()
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            attachments.append((f"file{len(attachments)}", (path.name, data, mime)))
        except Exception as exc:
            log.warning("attach_sample_failed", path=str(path), error=str(exc))
        if len(attachments) >= 3:
            break

    async with httpx.AsyncClient(timeout=20) as cli:
        await cli.post(
            WEBHOOK_GENERAL,
            data={"content": content},
            files=attachments or None
        )
    log.info(
        "learning_snapshot_posted",
        attachments=len(attachments),
        buckets=len(samples[0].get("buckets", [])) if samples else 0,
        eval_accuracy=eval_snapshot.get("accuracy") if eval_snapshot else None,
    )
    LEARNING_POSTS.inc()
    events.record_event("learning_snapshot", {
        "attachments": len(attachments),
        "buckets": len(samples[0].get("buckets", [])) if samples else 0,
        "accuracy": eval_snapshot.get("accuracy") if eval_snapshot else None,
    })
    return {"ok": True, "posted": True, "attachments": len(attachments)}


@app.get("/api/events")
def get_events(limit: int = 50):
    try:
        lim = max(1, min(int(limit), 200))
    except ValueError:
        lim = 50
    data = events.list_events(lim)
    return {"events": data}

@app.get('/draft/{item_id}', response_class=HTMLResponse)
def view_draft(item_id: int, request: Request):
    with connect() as c:
        attrs = {r['field']: {'value': r['value'], 'confidence': r['confidence']}
                 for r in c.execute('select * from attributes where item_id=?', (item_id,))}
        draft = c.execute('select * from drafts where item_id=?', (item_id,)).fetchone()
        photos = c.execute('select * from photos where item_id=?', (item_id,)).fetchall()
        price = c.execute('select * from prices where item_id=?', (item_id,)).fetchone()
    d = {
        'id': item_id,
        'title': draft['title'] if draft else '',
        'price': (draft['price_pence']/100) if (draft and draft['price_pence']) else None,
        'brand': attrs.get('brand'), 'size': attrs.get('size'),
        'item_type': attrs.get('item_type'), 'colour': attrs.get('colour'),
        'thumbs': [f'/static/thumbs/{Path(p["optimised_path"]).stem}.jpg' for p in photos],
        'rec_price': (price['recommended_pence']/100) if price and price['recommended_pence'] else None,
    }
    return tmpl.TemplateResponse('draft.html', {'request': request, 'd': d})

@app.get('/api/drafts', response_model=List[DraftSummarySchema])
def list_drafts(status: Optional[str] = None):
    with connect() as c:
        query = 'select * from drafts'
        params: List[Any] = []
        if status:
            query += ' where status=?'
            params.append(status)
        query += ' order by coalesce(updated_at, created_at, 0) desc, item_id desc'
        rows = c.execute(query, params).fetchall()
        payloads = []
        for row in rows:
            photos = _fetch_photos(c, row['item_id'], limit=1)
            payloads.append(_serialize_draft_row(row, photos, include_photos=False))
    return payloads

@app.get('/api/drafts/{draft_id}', response_model=DraftResponseSchema)
def get_draft_detail(draft_id: int):
    payload = _load_draft_payload(draft_id, include_photos=True)
    if not payload:
        raise HTTPException(status_code=404, detail="Draft not found")
    return payload

@app.put('/api/drafts/{draft_id}', response_model=DraftResponseSchema)
async def update_draft_api(draft_id: int, payload: DraftUpdatePayload):
    updates: Dict[str, Any] = {}
    if payload.title is not None:
        updates["title"] = _sanitize_attr(payload.title, 80)
    if payload.description is not None:
        updates["description"] = _sanitize_attr(payload.description, 400)
    if payload.status is not None:
        updates["status"] = payload.status.strip()
    if payload.category_id is not None:
        updates["category_id"] = payload.category_id.strip()
    if payload.category_name is not None:
        updates["category_name"] = payload.category_name.strip()
    price_value = payload.selected_price
    if price_value is None:
        price_value = payload.price
    if price_value is not None:
        updates["selected_price_pence"] = _gbp_to_pence(price_value)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update.")
    updates["updated_at"] = now()
    set_clause = ", ".join(f"{field}=?" for field in updates)
    params = list(updates.values()) + [draft_id]
    with connect() as c:
        row = c.execute('select 1 from drafts where item_id=?', (draft_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Draft not found")
        c.execute(f'update drafts set {set_clause} where item_id=?', params)
        if "status" in updates:
            c.execute('update items set status=?, updated_at=? where id=?', (updates["status"], updates["updated_at"], draft_id))
        c.commit()
    payload = _load_draft_payload(draft_id, include_photos=True)
    if not payload:
        raise HTTPException(status_code=404, detail="Draft not found")
    return payload

@app.post('/api/infer')
async def infer_image(request: Request, file: UploadFile = File(...)):
    if file is None:
        raise HTTPException(status_code=400, detail="file is required")
    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="empty file payload")

    tmp_id = uuid4().hex
    suffix = Path(file.filename or "").suffix or ".bin"
    raw_path = INFER_TMP / f"{tmp_id}{suffix}"
    raw_path.write_bytes(blob)
    jpeg_path = raw_path.with_suffix('.jpg')

    ok = await asyncio.to_thread(to_jpeg, raw_path, jpeg_path)
    if not ok:
        _cleanup_temp_files(raw_path, jpeg_path)
        raise HTTPException(status_code=422, detail="Unable to process this image type.")

    fast_mode = str(request.query_params.get("fast", "0")).lower() in {"1", "true", "yes"}

    if fast_mode:
        label_text = ""
        brand = size = None
        bconf = sconf = 'Low'
    else:
        label_text = await asyncio.to_thread(ocr.read_text, jpeg_path)
        brand, bconf, size, sconf = detect_brand_size(label_text)
    name_hint = file.filename or label_text or "clothing"
    colour = await asyncio.to_thread(dominant_colour, jpeg_path)
    item_type, iconf = item_type_from_name(name_hint)

    tags = [t for t in (brand, size, colour, item_type) if t]
    response: Dict[str, Any] = {
        "category": item_type,
        "item_type": {"value": item_type, "confidence": iconf},
        "brand": {"value": brand or "", "confidence": bconf},
        "size": {"value": size or "", "confidence": sconf},
        "colour": {"value": colour, "confidence": "Medium"},
        "label_text": label_text,
        "tags": tags,
        "source": "pi-local",
        "fast_mode": fast_mode,
    }
    if any((brand, item_type, size, colour)):
        price_estimate = await pricing_service.suggest_price(
            brand=brand,
            category=item_type,
            size=size,
            colour=colour,
            condition="Good",
        )
    else:
        price_estimate = PriceEstimate()

    if price_estimate.has_prices:
        response["price"] = price_estimate.as_response()
    if price_estimate.examples:
        response["examples"] = price_estimate.examples

    _cleanup_temp_files(raw_path, jpeg_path)
    return response

@app.post('/api/upload')
async def upload(request: Request,
                 background_tasks: BackgroundTasks,
                 files: List[UploadFile] = File(...),
                 metadata: Optional[str] = Form(None)):
    _require_upload_auth(request)
    _enforce_upload_rate_limit(request)
    meta_payload: Optional[Dict[str, Any]] = None
    if metadata:
        try:
            meta_payload = json.loads(metadata)
        except json.JSONDecodeError:
            log.warning("discarding malformed metadata payload for upload: %s", metadata[:200])

    item_id = _create_item()
    saved = await _save_upload_files(item_id, files)
    if meta_payload:
        _write_ingest_meta(item_id, meta_payload)

    # Kick off background processing and return immediately
    background_tasks.add_task(_process_item, item_id, saved)
    return {"queued": True, "item_id": item_id}

@app.post('/api/drafts', response_model=DraftResponseSchema, status_code=201)
async def create_draft(
    request: Request,
    files: List[UploadFile] = File(...),
    metadata: Optional[str] = Form(None),
):
    _require_upload_auth(request)
    _enforce_upload_rate_limit(request)
    if not files:
        raise HTTPException(status_code=400, detail="At least one image is required.")
    meta_payload: Optional[Dict[str, Any]] = None
    if metadata:
        try:
            meta_payload = json.loads(metadata)
        except json.JSONDecodeError:
            log.warning("discarding malformed metadata payload for draft upload: %s", metadata[:200])
    item_id = _create_item()
    saved = await _save_upload_files(item_id, files)
    if meta_payload:
        _write_ingest_meta(item_id, meta_payload)
    start = time.time()
    try:
        draft = await ingest_service.build_draft(
            item_id=item_id,
            filepaths=saved,
            metadata=meta_payload,
        )
    except DraftRejected as exc:
        await _reject_item(item_id, list(exc.reasons))
        raise HTTPException(status_code=422, detail={"reasons": exc.reasons})
    await _store_ingest_result(item_id, draft, started_at=start)
    payload = _load_draft_payload(item_id, include_photos=True)
    if not payload:
        raise HTTPException(status_code=500, detail="Unable to load stored draft.")
    return payload

@app.post('/api/draft/{item_id}/save')
async def save_draft(item_id: int, title: str = Form(''), brand: str = Form(''), size: str = Form(''),
                     item_type: str = Form(''), colour: str = Form(''), condition: str = Form(''), price: str = Form('')):
    with connect() as c:
        existing_attrs = {r['field']: r['value'] for r in c.execute('select field,value from attributes where item_id=?', (item_id,))}
    clean_vals = {
        'brand': _sanitize_attr(brand, 60),
        'size': _sanitize_attr(size, 24),
        'item_type': _sanitize_attr(item_type, 40),
        'colour': _sanitize_attr(colour, 24),
        'condition': _normalize_condition(condition),
    }
    auto_title = _make_listing_title(
        clean_vals['brand'] or existing_attrs.get('brand'),
        clean_vals['item_type'] or existing_attrs.get('item_type') or 'clothing',
        clean_vals['colour'] or existing_attrs.get('colour') or '',
        clean_vals['size'] or existing_attrs.get('size')
    )
    clean_title = _sanitize_attr(title, 80) or auto_title
    if len(clean_title) < 5:
        clean_title = auto_title
    price_pence = _clamp_price(_price_to_pence(price))

    with connect() as c:
        c.execute('insert or replace into drafts(item_id, title, price_pence) values (?,?,?)',
                  (item_id, clean_title, price_pence))
        for field, value in clean_vals.items():
            c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)',
                      (item_id, field, value, 'User'))
        row = c.execute('select value from attributes where item_id=? and field=?', (item_id, 'label_text')).fetchone()
        if row:
            text = row['value']
            lhash = _label_hash(text)
            c.execute('insert or replace into learned_labels(label_hash, brand, size, seen_text, created_at) values (?,?,?,?,?)',
                      (lhash, clean_vals['brand'] or '', clean_vals['size'] or '', text, now()))
            payload = json.dumps({"label_hash": lhash, "brand": clean_vals['brand'], "size": clean_vals['size'], "seen_text": text})
            c.execute('insert into learning_events(kind, payload_json, created_at, synced_at) values (?,?,?,NULL)',
                      ('label_learning', payload, now()))
        c.commit()
    return RedirectResponse(url=f'/draft/{item_id}', status_code=303)

@app.post('/api/draft/{item_id}/check_price')
async def check_price(item_id: int):
    if not COMPS_BASE:
        return RedirectResponse(url=f'/draft/{item_id}', status_code=303)
    with connect() as c:
        attrs = {r['field']: r['value'] for r in c.execute('select field,value from attributes where item_id=?', (item_id,))}
    params = {
        'brand': attrs.get('brand',''),
        'item_type': attrs.get('item_type',''),
        'size': attrs.get('size',''),
        'colour': attrs.get('colour','')
    }
    price_estimate = await pricing_service.suggest_price(
        brand=params.get('brand'),
        category=params.get('item_type'),
        size=params.get('size'),
        colour=params.get('colour'),
        condition=attrs.get('condition') or 'Good',
    )
    rec = _gbp_to_pence(price_estimate.mid)
    p25 = _gbp_to_pence(price_estimate.low)
    p75 = _gbp_to_pence(price_estimate.high)
    examples = price_estimate.examples

    with connect() as c:
        if rec is not None:
            c.execute('insert or replace into prices(item_id, recommended_pence, p25_pence, p75_pence, checked_at) values (?,?,?,?,?)',
                      (item_id, rec, p25, p75, now()))
            c.execute('delete from comps where item_id=?', (item_id,))
            for ex in examples:
                c.execute('insert into comps(item_id,title,price_pence,url) values (?,?,?,?)',
                          (item_id, ex.get('title',''), int(float(ex.get('price_gbp',0))*100), ex.get('url','')))
            c.commit()
    return RedirectResponse(url=f'/draft/{item_id}', status_code=303)
@app.get('/draft/{item_id}/export')
def export_draft(item_id: int):
    return build_listing_pack(item_id)
