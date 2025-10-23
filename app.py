import io, os, time, re, json, logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, request, jsonify
from PIL import Image, ImageEnhance, ImageOps
import numpy as np

import torch
import easyocr
from rapidfuzz import process as fz_process, fuzz as fz

# FashionCLIP (optional) → OpenCLIP fallback
FCLIP_AVAILABLE = False
try:
    from fashion_clip.fashion_clip import FashionCLIP
    FCLIP_AVAILABLE = True
except Exception:
    FCLIP_AVAILABLE = False

import open_clip

# Optional (wired but safe if missing)
try:
    import price_fetcher
except Exception:
    price_fetcher = None

__version__ = "0.9.0"

# ---------------------------- Config ----------------------------
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

# thresholds
TYPE_CONF_MIN = float(os.getenv("TYPE_CONF_MIN", "0.45"))
BRAND_CONF_MIN = float(os.getenv("BRAND_CONF_MIN", "0.65"))
OCR_TIMEOUT_SECS = int(os.getenv("OCR_TIMEOUT_SECS", "45"))  # overall budget

# size patterns
ADULT_SIZE_PATTERNS = [
    r"\b(UK|EU|EUR|US|FR)\s?(XXS|XS|S|M|L|XL|XXL|2XL|3XL|4XL)\b",
    r"\b(XXS|XS|S|M|L|XL|XXL|2XL|3XL|4XL)\b",
    r"\b\d{2}W\s?\d{2}L\b",
    r"\b(EUR|EU)\s?\d{2}\b",
    r"\bUK\s?\d{1,2}\b",
]

CHILD_SIZE_PATTERNS = [
    r"\b\d{1,2}\s?-\s?\d{1,2}\s?(m|M|months|Months|MONTHS)\b",
    r"\b\d{1,2}\s?-\s?\d{1,2}\s?(yrs|Yrs|Years|years|YRS)\b",
    r"\b(age|Age)\s?\d{1,2}\b",
    r"\b\d{1,2}(m|M|Y|y)\b",
    r"\b\d{1,2}\s?(?:years|yrs|y)\b",
]

DOMAIN_LABELS = ["clothing", "electronics"]

CLOTHING_TYPES = [
    "t-shirt", "hoodie", "sweatshirt", "jumper", "cardigan", "shirt",
    "jacket", "coat", "gilet", "dress", "skirt", "jeans", "trousers", "shorts",
    "tracksuit bottoms", "leggings", "suit", "blazer", "polo shirt", "tank top",
    "activewear top", "activewear leggings", "sports bra", "underwear",
    "trainers", "shoes", "boots", "sandals", "heels", "hat", "cap"
]
ELECTRONICS_TYPES = [
    "phone", "smartphone", "laptop", "tablet", "camera", "headphones", "earbuds",
    "speaker", "game console", "controller", "smartwatch", "monitor"
]

CATEGORY_MAP = {
    "t-shirt": "Clothing → T-shirts & Tops",
    "polo shirt": "Clothing → T-shirts & Tops",
    "tank top": "Clothing → T-shirts & Tops",
    "shirt": "Clothing → Shirts",
    "hoodie": "Clothing → Hoodies & Jumpers",
    "sweatshirt": "Clothing → Hoodies & Jumpers",
    "jumper": "Clothing → Hoodies & Jumpers",
    "cardigan": "Clothing → Hoodies & Jumpers",
    "jacket": "Clothing → Jackets & Coats",
    "coat": "Clothing → Jackets & Coats",
    "gilet": "Clothing → Jackets & Coats",
    "dress": "Clothing → Dresses",
    "skirt": "Clothing → Skirts",
    "jeans": "Clothing → Jeans",
    "trousers": "Clothing → Trousers",
    "shorts": "Clothing → Shorts",
    "tracksuit bottoms": "Clothing → Tracksuits",
    "leggings": "Clothing → Leggings",
    "suit": "Clothing → Suits & Blazers",
    "blazer": "Clothing → Suits & Blazers",
    "activewear top": "Sportswear",
    "activewear leggings": "Sportswear",
    "sports bra": "Sportswear",
    "underwear": "Underwear",
    "trainers": "Shoes → Trainers",
    "shoes": "Shoes",
    "boots": "Shoes → Boots",
    "sandals": "Shoes → Sandals",
    "heels": "Shoes → Heels",
    "hat": "Accessories → Hats",
    "cap": "Accessories → Hats",
}
BRANDS = [
    "Nike","Adidas","Puma","Reebok","New Balance","Asics","Under Armour","The North Face",
    "Patagonia","Columbia","Levi's","Tommy Hilfiger","Ralph Lauren","Lacoste","Carhartt",
    "Supreme","Stüssy","Champion","H&M","Zara","Uniqlo","COS","Arket","Weekday","Pull&Bear",
    "Bershka","Next","River Island","Jack & Jones","Superdry","AllSaints","Moncler","Canada Goose",
    "Stone Island","CP Company","Barbour","Dr. Martens","Converse","Vans","Birkenstock",
    "Gucci","Prada","Balenciaga","Louis Vuitton","Yeezy","Off-White","BOSS","Hugo","Diesel",
    "G-Star RAW","Alpha Industries","Berghaus","Rab","Arc'teryx","Nike SB","Jordan","EA7",
    "Primark","George","F&F","M&S","Tu","John Lewis","Gap","Next Kids","Zara Kids","H&M Kids"
]
BRANDS_LOWER = [b.lower() for b in BRANDS]
ELECTRONICS_BRANDS = {"Apple","Samsung","Sony","Canon","Nikon","Bose","Beats","Huawei","Xiaomi","Dell","HP","Lenovo"}

# ---------------------------- Logging ----------------------------
logger = logging.getLogger("VintedAICloud")
logger.setLevel(logging.INFO)
fh = RotatingFileHandler(LOG_DIR / "server.log", maxBytes=2_000_000, backupCount=3)
fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter("🔹 %(message)s"))
logger.addHandler(fh); logger.addHandler(ch)

# ---------------------------- Models ----------------------------
device = "cpu"  # Render free tier → CPU only
reader = easyocr.Reader(["en"], gpu=False)

fclip = None
if FCLIP_AVAILABLE:
    try:
        fclip = FashionCLIP("fashion-clip", device=device)
        logger.info("FashionCLIP loaded.")
    except Exception as e:
        logger.warning(f"FashionCLIP unavailable: {e}; using OpenCLIP only.")

oc_model, _, oc_preprocess = open_clip.create_model_and_transforms("ViT-B-32", pretrained="openai")
oc_tokenizer = open_clip.get_tokenizer("ViT-B-32")
oc_model.to(device).eval()
logger.info("OpenCLIP ViT-B-32 loaded.")
server_start = time.time()

# ---------------------------- Helpers ----------------------------
def pil_to_tensor(pil):
    return oc_preprocess(pil).unsqueeze(0).to(device)

def clip_text_embed(texts):
    toks = oc_tokenizer(texts).to(device)
    with torch.no_grad():
        t = oc_model.encode_text(toks)
        t = t / t.norm(dim=-1, keepdim=True)
    return t

def openclip_image_embed(pil):
    img = pil_to_tensor(pil)
    with torch.no_grad():
        v = oc_model.encode_image(img)
        v = v / v.norm(dim=-1, keepdim=True)
    return v

def fclip_image_embed(pil):
    with torch.no_grad():
        feats = fclip.encode_images([pil], device=device, batch_size=1)
        v = torch.tensor(feats, device=device, dtype=torch.float32)
        v = v / v.norm(dim=-1, keepdim=True)
    return v

def zero_shot(pil, labels):
    prompts = [f"a photo of {l}" for l in labels]
    if fclip:
        imgf = fclip_image_embed(pil)
        txt = torch.tensor(fclip.encode_text(prompts, device=device), device=device, dtype=torch.float32)
        txt = txt / txt.norm(dim=-1, keepdim=True)
    else:
        imgf = openclip_image_embed(pil)
        txt = clip_text_embed(prompts)
    with torch.no_grad():
        sims = (100.0 * imgf @ txt.T).softmax(dim=-1)
    arr = sims.squeeze(0).detach().cpu().numpy().tolist()
    idx = int(np.argmax(arr))
    return {"label": labels[idx], "confidence": float(arr[idx]), "ranked": list(zip(labels, arr))}

def multi_crop_ocr(pil, budget_seconds=OCR_TIMEOUT_SECS):
    """OCR on key regions (neck/tag, chest/logo, full). Time-bounded."""
    t0 = time.time()
    w, h = pil.size
    regions = [
        (int(0.15*w), int(0.02*h), int(0.85*w), int(0.22*h)),
        (int(0.20*w), int(0.25*h), int(0.80*w), int(0.45*h)),
        (0, 0, w, h),
    ]
    texts = []
    for (x1,y1,x2,y2) in regions:
        if time.time() - t0 > budget_seconds:
            break
        crop = pil.crop((x1,y1,x2,y2))
        crop = ImageEnhance.Brightness(crop).enhance(1.2)
        crop = ImageEnhance.Contrast(crop).enhance(1.8)
        try:
            res = reader.readtext(np.array(crop))
            if res:
                texts.extend([r[1] for r in res])
        except Exception:
            continue
    return " ".join(texts).strip()

def normalise_brand(ocr_text):
    if not ocr_text:
        return "", 0.0
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9'&\-]{1,}", ocr_text)
    candidates = list({t.lower() for t in tokens if len(t) >= 2})[:16]
    if not candidates:
        return "", 0.0
    match, score, _ = fz_process.extractOne(" ".join(candidates), BRANDS_LOWER, scorer=fz.token_set_ratio)
    if score < 60:  # a bit lower to catch noisy tags
        return "", score/100.0
    return BRANDS[BRANDS_LOWER.index(match)], score/100.0

def extract_size_and_age(ocr_text):
    if not ocr_text:
        return "Not visible", "unknown"
    # child first
    for pat in CHILD_SIZE_PATTERNS:
        m = re.search(pat, ocr_text, flags=re.IGNORECASE)
        if m:
            return m.group(0).strip(), "child"
    # then adult
    for pat in ADULT_SIZE_PATTERNS:
        m = re.search(pat, ocr_text, flags=re.IGNORECASE)
        if m:
            return m.group(0).strip().upper(), "adult"
    return "Not visible", "unknown"

def color_hint_simple(pil):
    arr = np.array(pil).reshape(-1, 3).astype(np.float32)
    mean = arr.mean(axis=0); overall = mean.mean()
    if overall < 70: return "Black"
    if overall < 110: return "Dark Grey"
    if overall > 200: return "White"
    if mean[0] > mean[1] and mean[0] > mean[2]: return "Red-ish"
    if mean[1] > mean[0] and mean[1] > mean[2]: return "Green-ish"
    if mean[2] > mean[0] and mean[2] > mean[1]: return "Blue-ish"
    return "Neutral"

def vinted_category_for(item_label):
    return CATEGORY_MAP.get(item_label, "Clothing" if item_label in CLOTHING_TYPES else ("Electronics" if item_label in ELECTRONICS_TYPES else "Other"))

def analyse_one(pil_img):
    # Enhance upfront
    base = ImageEnhance.Brightness(pil_img).enhance(1.15)
    base = ImageEnhance.Contrast(base).enhance(1.45)

    # Domain → Type
    dom = zero_shot(base, DOMAIN_LABELS)
    domain = dom["label"]
    labels = CLOTHING_TYPES if domain == "clothing" else ELECTRONICS_TYPES
    fine = zero_shot(base, labels)
    item_type = fine["label"]
    type_conf = fine["confidence"]

    # OCR multi-rotation (bounded)
    all_text = []
    for angle in (0, 90, 180, 270):
        rotated = base.rotate(angle, expand=True)
        all_text.append(multi_crop_ocr(rotated, budget_seconds=OCR_TIMEOUT_SECS // 4))
    ocr_text = " ".join([t for t in all_text if t]).strip()

    brand_norm, brand_conf = normalise_brand(ocr_text)
    size, age_group = extract_size_and_age(ocr_text)

    # Sanity corrections from OCR keywords
    ltxt = ocr_text.lower()
    for keyword in ["jacket", "hoodie", "t-shirt", "shirt", "coat", "jeans", "dress", "skirt"]:
        if keyword in ltxt:
            item_type = keyword
            type_conf = max(type_conf, 0.70)
            break
    if "primark" in ltxt:
        brand_norm, brand_conf = "Primark", max(brand_conf, 0.9)

    if domain == "electronics" and brand_norm and brand_norm not in ELECTRONICS_BRANDS:
        domain = "clothing"

    review_needed = []
    if type_conf < TYPE_CONF_MIN:
        review_needed.append("item_type")
    if not brand_norm or brand_conf < BRAND_CONF_MIN:
        review_needed.append("brand")
    if size == "Not visible":
        review_needed.append("size")

    colour = color_hint_simple(base)
    category = vinted_category_for(item_type)

    return {
        "domain": domain,
        "item_type": item_type,
        "type_confidence": round(type_conf, 3),
        "brand": brand_norm if brand_norm else "Unknown",
        "brand_confidence": round(brand_conf, 3),
        "size": size,
        "age_group": age_group,
        "colour": colour,
        "ocr_text": ocr_text,
        "category": category,
        "needs_review": review_needed
    }

# ---------------------------- Flask ----------------------------
app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status":"ok","uptime": round(time.time()-server_start,2),"version":__version__})

@app.route("/upload", methods=["POST"])
def upload():
    try:
        if "file" not in request.files:
            return jsonify({"error":"no file"}), 400
        f = request.files["file"]
        pil = Image.open(io.BytesIO(f.read())).convert("RGB")
    except Exception as e:
        logger.exception("Invalid image")
        return jsonify({"error":"invalid image","details":str(e)}), 400

    t0 = time.time()
    res = analyse_one(pil)

    # Build listing
    brand = res["brand"]
    item_type = res["item_type"]
    colour = res["colour"]
    size = res["size"]
    age_group = res["age_group"]
    category = res["category"]

    title_bits = []
    if brand != "Unknown":
        title_bits.append(brand)
    title_bits.append(item_type.title())
    if age_group == "child":
        title_bits.append("(Kids)")
    title_bits.append(f"- {colour}")
    title = " ".join(title_bits)

    desc_lines = []
    lead = f"{brand if brand!='Unknown' else ''} {item_type} in {colour.lower()} colour.".strip()
    desc_lines.append(lead[0].upper() + lead[1:] if lead else item_type.title())
    desc_lines.append(f"Size: {size}." if size and size != "Not visible" else "Size not visible in photos.")
    desc_lines.append("Lightly used, no major marks. Fast postage, smoke-free home.")
    description = " ".join(desc_lines)

    # Price suggestion (optional now; wired for later)
    price_block = None
    missing = res["needs_review"].copy()
    if not missing and price_fetcher:
        try:
            price_block = price_fetcher.get_vinted_price(brand, item_type, size=size, age_group=age_group)
        except Exception as e:
            logger.warning(f"Price fetch failed: {e}")

    price_text = None
    if price_block and price_block.get("count", 0) >= 5:
        price_text = f"£{price_block['median']} (range £{price_block['min']}–£{price_block['max']} based on {price_block['count']} Vinted UK listings)"
    else:
        price_text = None if missing else "TBD (no comps found yet)"

    out = {
        "title": title,
        "brand": brand,
        "size": size,
        "age_group": age_group,
        "colour": colour,
        "category": category,
        "condition": "Good",
        "description": description,
        "price_suggestion": price_text,
        "analysis_time": round(time.time()-t0,2),
        "debug": {"analysis": res}
    }
    return jsonify(out)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)
