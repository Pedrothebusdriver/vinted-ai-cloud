import os, sys, json, glob, time, pathlib, requests, mimetypes
from datetime import datetime

# Config via env (edit in repo Variables later if you like)
WEBHOOK = os.environ.get("DISCORD_AGENT_WEBHOOK", "").strip()
INFER_URL = os.environ.get("PI_INFER_URL", "http://127.0.0.1:8080/api/infer").strip()
ROOT = pathlib.Path("data/online-samples")
EVAL_OUT = pathlib.Path("data/evals")

def pick_category(j):
    # Robust extraction from various response shapes
    for keypath in [
        ("item_type","value"), ("category",), ("predicted_category",),
        ("itemType",), ("label","item_type")
    ]:
        cur = j
        try:
            for k in keypath: cur = cur[k]
            if isinstance(cur, str) and cur.strip():
                return cur.strip().lower()
        except Exception:
            pass
    return ""

def pick_tags(j):
    t = j.get("tags") or j.get("labels") or []
    if isinstance(t, dict): t = list(t.values())
    if not isinstance(t, list): t = []
    tags = []
    for x in t:
        if isinstance(x, str): tags.append(x)
        elif isinstance(x, dict):
            v = x.get("value") or x.get("name")
            if isinstance(v, str): tags.append(v)
    return list(dict.fromkeys([s.strip() for s in tags if s and isinstance(s,str)]))[:8]

def pick_price(j):
    # Try a few shapes
    for keypath in [("price",), ("pricing","price"), ("price","value")]:
        cur = j
        try:
            for k in keypath: cur = cur[k]
            if isinstance(cur,(int,float,str)) and str(cur):
                return float(str(cur).replace("£","").replace("$","").replace("€",""))
        except Exception:
            pass
    return None

def infer_one(img_path: pathlib.Path):
    with open(img_path, "rb") as f:
        r = requests.post(INFER_URL, files={"file": (img_path.name, f, mimetypes.guess_type(img_path.name)[0] or "application/octet-stream")}, timeout=45)
    r.raise_for_status()
    j = r.json()
    return {
        "category": pick_category(j),
        "tags": pick_tags(j),
        "price": pick_price(j),
        "raw": j,
    }

def post_to_discord(img_path: pathlib.Path, msg: str):
    if not WEBHOOK: 
        return
    with open(img_path, "rb") as f:
        files = {"file": (img_path.name, f, mimetypes.guess_type(img_path.name)[0] or "application/octet-stream")}
        data = {"content": msg}
        requests.post(WEBHOOK, data=data, files=files, timeout=45)

def main():
    # Today’s folder(s)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    roots = [ROOT / today]
    # If nothing for today, look at the most recent dated folder
    if not roots[0].exists():
        dated = sorted([p for p in ROOT.glob("*") if p.is_dir()], reverse=True)
        if dated: roots = [dated[0]]

    imgs = []
    for r in roots:
        imgs += [p for p in r.glob("**/*") if p.suffix.lower() in {".jpg",".jpeg",".png",".webp"}]
    # Cap to avoid spamming Discord
    imgs = imgs[:12]

    if not imgs:
        print("No images to evaluate.")
        return

    date_dir = EVAL_OUT / today
    date_dir.mkdir(parents=True, exist_ok=True)
    results_path = date_dir / "eval-results.jsonl"

    ok, total = 0, 0
    lines = []
    for img in imgs:
        # Bucket is the folder after the date segment
        parts = img.relative_to(ROOT).parts  # YYYY-MM-DD / bucket / file
        expected_bucket = parts[1] if len(parts) >= 3 else ""
        try:
            pred = infer_one(img)
            cat = (pred["category"] or "").lower()
            is_correct = (expected_bucket.split("/",1)[-1].split("-")[0] in cat) if expected_bucket else False
            total += 1
            if is_correct: ok += 1
            one = {
                "file": str(img),
                "bucket": expected_bucket,
                "pred_category": cat,
                "pred_tags": pred["tags"],
                "pred_price": pred["price"],
                "correct": bool(is_correct),
                "ts": datetime.utcnow().isoformat()+"Z"
            }
            lines.append(one)

            # Discord line (short)
            tag_str = ", ".join(pred["tags"][:3]) if pred["tags"] else "-"
            price_str = f"£{pred['price']:.2f}" if isinstance(pred["price"], (int,float)) else "-"
            msg = (
                f"**Eval** `{expected_bucket}` → **{cat or '—'}** "
                f"{'✅' if is_correct else '❌'}\n"
                f"tags: {tag_str} | price: {price_str}"
            )
            post_to_discord(img, msg)

        except Exception as e:
            err = f"{type(e).__name__}: {e}"
            lines.append({"file": str(img), "bucket": expected_bucket, "error": err, "ts": datetime.utcnow().isoformat()+"Z"})
            post_to_discord(img, f"**Eval error** on `{expected_bucket}` → `{img.name}`\n`{err}`")

    # Save eval lines
    with open(results_path, "a", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    # Summary to Discord
    if total:
        acc = 100.0*ok/total
        summary = f"**Eval summary** {ok}/{total} correct ({acc:.1f}%) on `{today}`"
        if WEBHOOK:
            requests.post(WEBHOOK, json={"content": summary}, timeout=20)
    print("Done.")

if __name__ == "__main__":
    main()
