from fastapi import FastAPI, UploadFile, File, Request, Form, BackgroundTasks
from app.export import build_listing_pack
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import httpx
import os, shutil, subprocess, asyncio, logging, re, json, hashlib, time
from typing import Optional, Tuple, List

from app.db import connect, init_db, now
from app.ocr import OCR
from app.classifier import dominant_colour, item_type_from_name

# ---------- Logging ----------
log = logging.getLogger("vinted-pi")
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")

# ---------- Env / paths ----------
load_dotenv()
WEBHOOK = os.getenv('DISCORD_WEBHOOK_URL', '')
COMPS_BASE = os.getenv('COMPS_BASE_URL', '')

BASE = Path('.')
INP = BASE / 'input_images'
OUT = BASE / 'converted_images'
BAK = BASE / 'backups'
THUMBS = BASE / 'static' / 'thumbs'
for p in (INP, OUT, BAK, THUMBS):
    p.mkdir(parents=True, exist_ok=True)

# Limit heavy conversions on small Pi
CONVERT_SEM = asyncio.Semaphore(1)

# ---------- FastAPI ----------
app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
tmpl = Jinja2Templates(directory='templates')
ocr = OCR()

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
    except Exception as e:
        log.warning("DB init warning: %s", e)

# ---------- Brand lexicon & helpers ----------
# If app/data/brands.json exists use it, else fallback to this seed list
_DEFAULT_BRANDS = [
    "Nike","Adidas","Puma","Reebok","New Balance","Asics","Under Armour","The North Face","TNF",
    "Columbia","Patagonia","Berghaus","Arc'teryx","Helly Hansen","Salomon","Hoka","Vans","Converse",
    "Levi's","Lee","Wrangler","Carhartt","Dickies","G-Star","Diesel","Zara","H&M","Uniqlo","Next",
    "ASOS","Boohoo","Bershka","Pull & Bear","Massimo Dutti","COS","Monki","Topshop","River Island",
    "AllSaints","Ralph Lauren","Tommy Hilfiger","Lacoste","Calvin Klein","Guess","Superdry","Hollister",
    "Abercrombie","Stone Island","CP Company","Barbour","Belstaff","Fred Perry","Ted Baker","Boss",
    "Michael Kors","Kate Spade","Coach","Balenciaga","Gucci","Prada","Louis Vuitton","Chanel"
]

try:
    BRANDS = json.loads((BASE/"app"/"data"/"brands.json").read_text())
    if not isinstance(BRANDS, list):
        BRANDS = _DEFAULT_BRANDS
except Exception:
    BRANDS = _DEFAULT_BRANDS

try:
    from rapidfuzz import process, fuzz
except Exception:
    process = None
    fuzz = None

BRAND_INDEX = None
if process:
    # Pre-build an index for faster lookups
    BRAND_INDEX = process.cdist.BFMatcher(BRANDS, scorer=fuzz.token_set_ratio)

_BRAND_MIN_SCORE_HIGH = 90
_BRAND_MIN_SCORE_MED = 80

SIZE_PATTERNS = [
    (re.compile(r"\b(XXS|XS|S|M|L|XL|XXL|XXXL)\b", re.I), lambda m: m.group(1).upper(), 'High'),
    (re.compile(r"\bUK\s?(\d{1,2})\b", re.I), lambda m: f"UK {m.group(1)}", 'High'),
    (re.compile(r"\bEU\s?(\d{2})\b", re.I), lambda m: f"EU {m.group(1)}", 'High'),
    (re.compile(r"\bUS\s?(\d{1,2})\b", re.I), lambda m: f"US {m.group(1)}", 'High'),
    (re.compile(r"\bW(\d{2})\s*[xX ]\s*L?(\d{2})\b", re.I), lambda m: f"W{m.group(1)} L{m.group(2)}", 'High'),
]

# ---------- OCR helpers ----------
def _preprocess_for_ocr(img_path: Path) -> Path:
    """Lightweight label boost: grayscale + autocontrast + threshold."""
    try:
        from PIL import ImageOps, ImageFilter, ImageEnhance
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
            if _run_im_cmd([str(src_path), '-auto-orient', '-resize', '1600x1600>', '-quality', '85', str(dst_path)]):
                return True
            img = Image.open(src_path).convert('RGB')
            img.thumbnail((1600, 1600))
            img.save(dst_path, quality=85)
            return True

        if _run_im_cmd([str(src_path), '-auto-orient', '-resize', '1600x1600>', '-quality', '85', str(dst_path)]):
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

def detect_brand_size(label_text: str) -> Tuple[Optional[str], str, Optional[str], str]:
    """Return (brand, brand_conf, size, size_conf)."""
    brand = None; bconf = 'Low'
    size = None; sconf = 'Low'

    nt = _normalize_text(label_text)

    # brand via RapidFuzz
    if process and BRAND_INDEX:
        match = BRAND_INDEX.extract_one(nt, BRANDS, scorer=fuzz.token_set_ratio)
        if match:
            name, score, _ = match
            if score >= _BRAND_MIN_SCORE_HIGH:
                brand, bconf = name, 'High'
            elif score >= _BRAND_MIN_SCORE_MED:
                brand, bconf = name, 'Medium'

    # size via regex patterns
    for rx, fn, conf in SIZE_PATTERNS:
        m = rx.search(label_text)
        if m:
            size = fn(m)
            sconf = conf
            break

    return brand, bconf, size, sconf

# ---------- Background job to process one item ----------
async def _process_item(item_id: int, filepaths: List[Path]) -> None:
    start = time.time()
    out_dir  = OUT / f'item-{item_id}'
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: List[Tuple[Path, Path]] = []

    async with CONVERT_SEM:  # serialize heavy work on Pi 3B+
        for src in filepaths:
            out_path = out_dir / Path(src.name).with_suffix('.jpg').name
            ok = await asyncio.to_thread(to_jpeg, src, out_path)
            if ok:
                await asyncio.to_thread(make_thumb, out_path, THUMBS / f'{out_path.stem}.jpg')
                paths.append((src, out_path))
            else:
                ph = Path('static/no-thumb.png')
                if ph.exists():
                    shutil.copyfile(ph, THUMBS / f'{out_path.stem}.jpg')

    # OCR on optimised JPEGs
    best_score, best_text, best_opt = -1, '', None
    for (_orig, opt) in paths:
        prep = _preprocess_for_ocr(opt)
        t = ocr.read_text(prep)
        score = sum(ch.isalnum() for ch in t)
        if score > best_score:
            best_score, best_text, best_opt = score, t, opt

    # learning lookup
    brand = size = None
    bconf = sconf = 'Low'
    label_text_norm = _normalize_text(best_text)
    lhash = _label_hash(best_text) if best_text else None
    with connect() as c:
        if lhash:
            row = c.execute('select brand, size from learned_labels where label_hash=?', (lhash,)).fetchone()
            if row:
                brand, size = row['brand'], row['size']
                bconf = sconf = 'High'

    # if not learned, run detectors
    if not brand or not size:
        dbrand, dbconf, dsize, dsconf = detect_brand_size(best_text)
        if not brand and dbrand:
            brand, bconf = dbrand, dbconf
        if not size and dsize:
            size, sconf = dsize, dsconf

    # Heuristics for type/colour
    first_name = filepaths[0].name if filepaths else 'clothing'
    item_type, iconf = item_type_from_name(first_name)
    colour = dominant_colour(paths[0][1]) if paths else 'Unknown'

    # Save to DB (also stash label_text for learning on save)
    with connect() as c:
        for orig, opt in paths:
            c.execute('insert into photos(item_id, original_path, optimised_path, width, height, is_label) values (?,?,?,?,?,0)',
                      (item_id, str(orig), str(opt), 0, 0))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'brand', brand or '', bconf))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'size', size or '', sconf))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'item_type', item_type, iconf))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'colour', colour, 'Medium'))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'label_text', best_text or '', 'Auto'))
        c.execute('insert or ignore into drafts(item_id, title, price_pence) values (?,?,?)', (item_id, '', None))
        c.commit()

    # Discord ping
    if WEBHOOK:
        try:
            async with httpx.AsyncClient(timeout=10) as cli:
                await cli.post(WEBHOOK, json={
                    'content': f'🧵 Draft ready: Item #{item_id} – http://localhost:8080/draft/{item_id}'
                })
        except Exception as e:
            log.warning("Discord webhook failed: %s", e)

    log.info("Item %s processed in %.2fs", item_id, time.time()-start)

# ---------- Routes ----------
@app.get('/health')
def health():
    return {"ok": True}

@app.get('/', response_class=HTMLResponse)
def home(request: Request):
    return tmpl.TemplateResponse('index.html', {'request': request})

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

@app.get('/api/drafts')
def list_drafts():
    with connect() as c:
        items = c.execute('select id from items order by id desc').fetchall()
    resp = []
    for it in items:
        iid = it['id']
        with connect() as c:
            attrs = {r['field']: {'value': r['value'], 'confidence': r['confidence']}
                     for r in c.execute('select * from attributes where item_id=?', (iid,))}
            draft = c.execute('select * from drafts where item_id=?', (iid,)).fetchone()
            photos = c.execute('select * from photos where item_id=?', (iid,)).fetchall()
        resp.append({
            'id': iid,
            'title': draft['title'] if draft else '',
            **attrs,
            'thumbs': [f'/static/thumbs/{Path(p["optimised_path"]).stem}.jpg' for p in photos]
        })
    return resp

@app.post('/api/upload')
async def upload(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    # Create item
    with connect() as c:
        c.execute('insert into items(status,created_at,updated_at) values(?,?,?)', ('draft', now(), now()))
        item_id = c.execute('select last_insert_rowid()').fetchone()[0]
        c.commit()

    # Folders
    item_dir = INP / f'item-{item_id}'
    bak_dir  = BAK / f'item-{item_id}'
    for p in (item_dir, bak_dir):
        p.mkdir(parents=True, exist_ok=True)

    # Save originals (stream to avoid big RAM spikes)
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

    # Kick off background processing and return immediately
    background_tasks.add_task(_process_item, item_id, saved)
    return {"queued": True, "item_id": item_id}

@app.post('/api/draft/{item_id}/save')
async def save_draft(item_id: int, title: str = Form(''), brand: str = Form(''), size: str = Form(''),
                     item_type: str = Form(''), colour: str = Form(''), condition: str = Form(''), price: str = Form('')):
    with connect() as c:
        c.execute('insert or replace into drafts(item_id, title, price_pence) values (?,?,?)',
                  (item_id, title, int(float(price)*100) if price else None))
        for k, v in {'brand': brand, 'size': size, 'item_type': item_type, 'colour': colour, 'condition': condition}.items():
            c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)',
                      (item_id, k, v, 'User'))
        # learning: pick stored label_text and upsert
        row = c.execute('select value from attributes where item_id=? and field=?', (item_id, 'label_text')).fetchone()
        if row:
            text = row['value']
            lhash = _label_hash(text)
            c.execute('insert or replace into learned_labels(label_hash, brand, size, seen_text, created_at) values (?,?,?,?,?)',
                      (lhash, brand or '', size or '', text, now()))
            payload = json.dumps({"label_hash": lhash, "brand": brand, "size": size, "seen_text": text})
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
    rec = None; p25=None; p75=None; examples=[]
    try:
        async with httpx.AsyncClient(timeout=20.0) as cli:
            for path in ('/api/price','/price'):
                r = await cli.get(COMPS_BASE.rstrip('/')+path, params=params)
                if r.status_code == 200:
                    data = r.json()
                    rec = int(float(data.get('median_price_gbp', 0))*100) if data.get('median_price_gbp') else None
                    p25 = int(float(data.get('p25_gbp', 0))*100) if data.get('p25_gbp') else None
                    p75 = int(float(data.get('p75_gbp', 0))*100) if data.get('p75_gbp') else None
                    examples = data.get('examples', [])[:5]
                    break
    except Exception as e:
        log.warning("Pricing fetch failed: %s", e)

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
