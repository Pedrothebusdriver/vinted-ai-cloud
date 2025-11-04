from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
from pathlib import Path
from PIL import Image, UnidentifiedImageError
import httpx
import os, shutil, subprocess, asyncio, logging

from app.db import connect, init_db, now
from app.ocr import OCR
from app.classifier import dominant_colour, item_type_from_name

# ---------- Logging ----------
log = logging.getLogger("vinted-pi")
logging.basicConfig(level=logging.INFO)

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
        log.info("DB ready at %s", d.DB_PATH)
    except Exception as e:
        log.warning("DB init warning: %s", e)

# ---------- Image helpers (DNG/HEIC/RAW -> JPEG) ----------
def _run_im_cmd(args: list[str]) -> bool:
    """Try ImageMagick (IM7 'magick' or IM6 'convert')."""
    for cmd in ('magick', 'convert'):
        try:
            subprocess.run([cmd] + args, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            return False
    return False

def _extract_dng_preview(src_path: Path, dst_path: Path) -> bool:
    """
    Fast path for iPhone/RAW DNG: extract the embedded JPEG preview using exiftool.
    Returns True if a usable JPEG was written to dst_path.
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    candidates = [
        ["exiftool", "-b", "-PreviewImage", str(src_path)],
        ["exiftool", "-b", "-JpgFromRaw", str(src_path)],
        ["exiftool", "-b", "-ThumbnailImage", str(src_path)],
    ]
    for cmd in candidates:
        try:
            data = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=15)
            if data and len(data) > 10_000:  # avoid tiny thumbnails
                with open(dst_path, "wb") as f:
                    f.write(data)
                return True
        except Exception:
            continue
    return False

def to_jpeg(src_path: Path, dst_path: Path) -> None:
    """Convert any image to a resized JPEG (1600px max). Prefers fast DNG preview."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    ext = src_path.suffix.lower()

    # Already a common raster? Use Pillow (fast + reliable)
    if ext in {'.jpg', '.jpeg', '.png'}:
        img = Image.open(src_path).convert('RGB')
        img.thumbnail((1600, 1600))
        img.save(dst_path, quality=85)
        return

    # FAST PATH for DNG: extract embedded preview with exiftool
    if ext == '.dng':
        if _extract_dng_preview(src_path, dst_path):
            return
        # Fall back to ImageMagick if preview not present
        ok = _run_im_cmd([str(src_path), '-auto-orient', '-resize', '1600x1600>', '-quality', '85', str(dst_path)])
        if ok:
            return
        # Last-ditch: Pillow (may fail on RAW)
        img = Image.open(src_path).convert('RGB')
        img.thumbnail((1600, 1600))
        img.save(dst_path, quality=85)
        return

    # HEIC/RAW and other formats – try ImageMagick first
    ok = _run_im_cmd([str(src_path), '-auto-orient', '-resize', '1600x1600>', '-quality', '85', str(dst_path)])
    if ok:
        return

    # Fallback to Pillow if IM fails
    img = Image.open(src_path).convert('RGB')
    img.thumbnail((1600, 1600))
    img.save(dst_path, quality=85)

def make_thumb(jpeg_path: Path, thumb_path: Path) -> None:
    thumb_path.parent.mkdir(parents=True, exist_ok=True)
    if not _run_im_cmd([str(jpeg_path), '-thumbnail', '128x128', str(thumb_path)]):
        img = Image.open(jpeg_path).copy()
        img.thumbnail((128, 128))
        img.save(thumb_path, quality=70)

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
async def upload(files: list[UploadFile] = File(...)):
    # Create item
    with connect() as c:
        c.execute('insert into items(status,created_at,updated_at) values(?,?,?)', ('draft', now(), now()))
        item_id = c.execute('select last_insert_rowid()').fetchone()[0]
        c.commit()

    # Folders
    item_dir = INP / f'item-{item_id}'
    out_dir  = OUT / f'item-{item_id}'
    bak_dir  = BAK / f'item-{item_id}'
    for p in (item_dir, out_dir, bak_dir):
        p.mkdir(parents=True, exist_ok=True)

    # Save + convert each file (offloaded to thread so we don't block)
    paths: list[tuple[Path, Path]] = []
    for f in files:
        dest = item_dir / f.filename
        with open(dest, 'wb') as w:
            w.write(await f.read())
        shutil.copyfile(dest, bak_dir / f.filename)

        out_path = out_dir / Path(f.filename).with_suffix('.jpg').name
        await asyncio.to_thread(to_jpeg, dest, out_path)
        await asyncio.to_thread(make_thumb, out_path, THUMBS / f'{out_path.stem}.jpg')
        paths.append((dest, out_path))

    # -------- Label OCR: use the OPTIMISED JPEGs (reliable for Tesseract) --------
    brand, bconf, size, sconf = None, 'Low', None, 'Low'
    if paths:
        best_score, best_text = -1, ""
        for (_orig, opt) in paths:
            t = ocr.read_text(opt)  # run on JPEG we just made
            score = sum(ch.isalnum() for ch in t)
            if score > best_score:
                best_score, best_text = score, t
        if best_score >= 0:
            b, bc, s, sc = ocr.extract_brand_size(best_text)
            brand, bconf, size, sconf = b, bc, s, sc

    # Heuristics for type/colour
    first_name = files[0].filename if files else 'clothing'
    item_type, iconf = item_type_from_name(first_name)
    colour = dominant_colour(paths[0][1]) if paths else 'Unknown'

    # Save to DB
    with connect() as c:
        for orig, opt in paths:
            c.execute('insert into photos(item_id, original_path, optimised_path, width, height, is_label) values (?,?,?,?,?,0)',
                      (item_id, str(orig), str(opt), 0, 0))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'brand', brand or '', bconf))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'size', size or '', sconf))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'item_type', item_type, iconf))
        c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)', (item_id,'colour', colour, 'Medium'))
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

    return {'message': f'Created draft #{item_id}', 'item_id': item_id}

@app.post('/api/draft/{item_id}/save')
async def save_draft(item_id: int, title: str = Form(''), brand: str = Form(''), size: str = Form(''),
                     item_type: str = Form(''), colour: str = Form(''), condition: str = Form(''), price: str = Form('')):
    with connect() as c:
        c.execute('insert or replace into drafts(item_id, title, price_pence) values (?,?,?)',
                  (item_id, title, int(float(price)*100) if price else None))
        for k, v in {'brand': brand, 'size': size, 'item_type': item_type, 'colour': colour, 'condition': condition}.items():
            c.execute('insert or replace into attributes(item_id, field, value, confidence) values (?,?,?,?)',
                      (item_id, k, v, 'User'))
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
