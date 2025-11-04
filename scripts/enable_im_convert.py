# scripts/enable_im_convert.py
# Enables DNG/HEIC/RAW conversion -> JPEG and improves label OCR photo selection.
# Idempotent; backs up app/main.py; prints what it changed.

import re
from pathlib import Path

MAIN = Path("pi-app/app/main.py")
backup = MAIN.with_suffix(".py.bak")

src = MAIN.read_text()

changed = False

# 1) Ensure 'subprocess' import exists
if "import subprocess" not in src:
    src = src.replace("from PIL import Image", "from PIL import Image\nimport subprocess")
    changed = True

# 2) Inject helper funcs (to_jpeg/make_thumb) once, just before "app = FastAPI()"
helpers = r'''
def _run_im_cmd(args):
    for cmd in ('magick', 'convert'):  # IM7 or IM6
        try:
            subprocess.run([cmd] + args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except FileNotFoundError:
            continue
        except subprocess.CalledProcessError:
            return False
    return False

def to_jpeg(src_path, dst_path):
    """Convert any image (DNG/HEIC/RAW/PNG/JPG) to a resized JPEG."""
    from PIL import Image
    src = Path(src_path); dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    ext = src.suffix.lower()
    if ext in {'.jpg', '.jpeg', '.png'}:
        img = Image.open(src).convert('RGB')
        img.thumbnail((1600,1600))
        img.save(dst, quality=85)
        return
    if not _run_im_cmd([str(src), '-auto-orient', '-resize', '1600x1600>', '-quality', '85', str(dst)]):
        img = Image.open(src).convert('RGB')  # last-ditch
        img.thumbnail((1600,1600))
        img.save(dst, quality=85)

def make_thumb(jpeg_path, thumb_path):
    from PIL import Image
    tp = Path(thumb_path); tp.parent.mkdir(parents=True, exist_ok=True)
    if not _run_im_cmd([str(jpeg_path), '-thumbnail', '128x128', str(tp)]):
        img = Image.open(jpeg_path).copy()
        img.thumbnail((128,128))
        img.save(tp, quality=70)
'''

if "def to_jpeg(" not in src:
    src = src.replace("app = FastAPI()", helpers + "\napp = FastAPI()")
    changed = True

# 3) Replace the Pillow-only conversion block in /api/upload with to_jpeg/make_thumb
pattern = re.compile(
    r"img\s*=\s*Image\.open\(dest\)\.convert\('RGB'\)\s*\n\s*"
    r"img\.thumbnail\(\(1600,1600\)\)\s*\n\s*"
    r"out_path\s*=\s*out_dir\s*/\s*Path\(f\.filename\)\.with_suffix\('\.jpg'\)\.name\s*\n\s*"
    r"img\.save\(out_path,\s*quality=85\)\s*\n\s*"
    r"th\s*=\s*img\.copy\(\)\s*\n\s*"
    r"th\.thumbnail\(\(128,128\)\)\s*\n\s*"
    r"th\.save\(THUMBS\s*/\s*f'\{out_path\.stem\}\.jpg',\s*quality=70\)\s*\n\s*"
    r"paths\.append\(\(dest,\s*out_path\)\)",
    re.S
)
replacement = (
    "out_path = out_dir / Path(f.filename).with_suffix('.jpg').name\n"
    "to_jpeg(dest, out_path)\n"
    "make_thumb(out_path, THUMBS / f'{out_path.stem}.jpg')\n"
    "paths.append((dest, out_path))"
)
src2, nrep = pattern.subn(replacement, src, count=1)
if nrep:
    src = src2
    changed = True

# 4) Improve label OCR: pick photo with most OCR-able text
label_pat = re.compile(
    r"(brand,\s*bconf,\s*size,\s*sconf\s*=\s*None,\s*'Low',\s*None,\s*'Low'\s*\n\s*)"
    r"if\s+paths:\s*\n(?:[^\n]*\n){1,12}?(\s*)item_type,\s*iconf\s*=\s*item_type_from_name",
    re.S
)
label_block = (
    r"\1"
    "if paths:\n"
    "        # Pick the image with the most OCR-able text as the label candidate\n"
    "        best_score, best_text = -1, \"\"\n"
    "        for (orig, _opt) in paths:\n"
    "            t = ocr.read_text(orig)\n"
    "            score = sum(ch.isalnum() for ch in t)\n"
    "            if score > best_score:\n"
    "                best_score, best_text = score, t\n"
    "        if best_score >= 0:\n"
    "            b, bc, s, sc = ocr.extract_brand_size(best_text)\n"
    "            brand, bconf, size, sconf = b, bc, s, sc\n"
    r"\2item_type, iconf = item_type_from_name"
)
src3, nlab = label_pat.subn(label_block, src, count=1)
if nlab:
    src = src3
    changed = True

if changed:
    backup.write_text(MAIN.read_text())
    MAIN.write_text(src)
    print("✅ Patched:", MAIN)
    print(f"   Backup saved at {backup}")
    print(f"   Blocks: conversion_replaced={bool(nrep)} label_patch={bool(nlab)}")
else:
    print("ℹ️ No changes needed; file already patched.")
