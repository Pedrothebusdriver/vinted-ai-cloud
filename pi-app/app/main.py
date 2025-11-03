from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import os, shutil
from pathlib import Path
from PIL import Image
import httpx
from app.db import connect, init_db, now
from app.ocr import OCR
from app.classifier import dominant_colour, item_type_from_name

load_dotenv()
WEBHOOK = os.getenv('DISCORD_WEBHOOK_URL', '')
COMPS_BASE = os.getenv('COMPS_BASE_URL', '')

BASE = Path('.')
INP = BASE/'input_images'
OUT = BASE/'converted_images'
BAK = BASE/'backups'
THUMBS = BASE/'static'/'thumbs'
THUMBS.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount('/static', StaticFiles(directory='static'), name='static')
tmpl = Jinja2Templates(directory='templates')
ocr = OCR()

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
    with connect() as c:
        c.execute('insert into items(status,created_at,updated_at) values(?,?,?)', ('draft', now(), now()))
        item_id = c.execute('select last_insert_rowid()').fetchone()[0]
        c.commit()

    item_dir = INP / f'item-{item_id}'
    item_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    for f in files:
        dest = item_dir / f.filename
        with open(dest, 'wb') as w:
            w.write(await f.read())
        bak = (BAK / f'item-{item_id}')
        bak.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(dest, bak / f.filename)
        out_dir = OUT / f'item-{item_id}'
        out_dir.mkdir(parents=True, exist_ok=True)
        img = Image.open(dest).convert('RGB')
        img.thumbnail((1600,1600))
        out_path = out_dir / Path(f.filename).with_suffix('.jpg').name
        img.save(out_path, quality=85)
        th = img.copy()
        th.thumbnail((128,128))
        th.save(THUMBS / f'{out_path.stem}.jpg', quality=70)
        paths.append((dest, out_path))

    brand, bconf, size, sconf = None, 'Low', None, 'Low'
    if paths:
        text = ocr.read_text(paths[-1][0])
        b, bc, s, sc = ocr.extract_brand_size(text)
        brand, bconf, size, sconf = b, bc, s, sc

    item_type, iconf = item_type_from_name(files[0].filename if files else 'clothing')
    colour = dominant_colour(paths[0][1]) if paths else 'Unknown'

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

    if WEBHOOK:
        try:
            import asyncio
            async def ping():
                async with httpx.AsyncClient(timeout=10) as cli:
                    await cli.post(WEBHOOK, json={'content': f'🧵 Draft ready: Item #{item_id} – http://localhost:8080/draft/{item_id}'})
            asyncio.get_event_loop().run_until_complete(ping())
        except Exception:
            pass

    return { 'message': f'Created draft #{item_id}', 'item_id': item_id }

@app.post('/api/draft/{item_id}/save')
async def save_draft(item_id: int, title: str = Form(''), brand: str = Form(''), size: str = Form(''),
                     item_type: str = Form(''), colour: str = Form(''), condition: str = Form(''), price: str = Form('')):
    with connect() as c:
        c.execute('insert or replace into drafts(item_id, title, price_pence) values (?,?,?)',
                  (item_id, title, int(float(price)*100) if price else None))
        for k,v in {'brand':brand,'size':size,'item_type':item_type,'colour':colour,'condition':condition}.items():
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
    except Exception:
        pass

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
