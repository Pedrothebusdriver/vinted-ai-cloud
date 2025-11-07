#!/usr/bin/env bash
set -euo pipefail

# Where to save images on the Pi (NOT committed)
OUT_ROOT="data/online-samples"
MAN_DIR=".agent/sampler"

# pick newest manifest produced by the Openverse step
MANIFEST="$(ls -1 ${MAN_DIR}/manifest-*.json 2>/dev/null | tail -n 1 || true)"
if [[ -z "${MANIFEST}" ]]; then
  echo "No manifest found in ${MAN_DIR}. Run the Openverse manifest workflow first."
  exit 1
fi

# run a tiny Python helper (stdlib only) to download & dedup by sha256
python3 - <<'PY'
import json, os, time, hashlib, re
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

OUT_ROOT = Path("data/online-samples")
MANIFEST = sorted(Path(".agent/sampler").glob("manifest-*.json"))[-1]

date_str = time.strftime("%Y-%m-%d", time.gmtime())
base = OUT_ROOT / date_str
base.mkdir(parents=True, exist_ok=True)

# persistent dedup index (NOT committed)
hash_idx_path = OUT_ROOT / ".sha256"
seen = set()
if hash_idx_path.exists():
    seen.update(x.strip() for x in hash_idx_path.read_text().splitlines() if x.strip())

def slug(x): return re.sub(r"[^a-z0-9/_-]+","-", x.lower())

def download(url: str) -> bytes|None:
    try:
        req = Request(url, headers={"User-Agent":"pi-vinted-agent/1.0"})
        with urlopen(req, timeout=25) as r:
            return r.read()
    except Exception:
        return None

mf = json.loads(Path(MANIFEST).read_text())
kept = dedup = errs = 0
by_bucket = {}

for b in mf.get("buckets", []):
    bucket = slug(b.get("bucket","misc"))
    outdir = base / bucket
    outdir.mkdir(parents=True, exist_ok=True)
    c = 0

    for it in b.get("items", []):
        url = it.get("url")
        if not url: 
            continue
        data = download(url)
        if not data:
            errs += 1
            continue

        h = hashlib.sha256(data).hexdigest()
        if h in seen:
            dedup += 1
            continue

        seen.add(h)
        # best-effort extension
        ext = os.path.splitext(urlparse(url).path)[1].lower()
        if not ext or len(ext) > 5: ext = ".jpg"
        (outdir / f"{h[:10]}{ext}").write_bytes(data)

        kept += 1; c += 1

    by_bucket[bucket] = c

# persist dedup set (rewrite to keep it small & clean)
hash_idx_path.write_text("\n".join(sorted(seen)) + "\n")

summary = {
    "ts": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
    "manifest": Path(MANIFEST).name,
    "saved_under": str(base),
    "kept": kept, "dedup": dedup, "errs": errs,
    "by_bucket": by_bucket,
}
out = Path(".agent/sampler") / f"summary-{summary['ts']}.json"
out.write_text(json.dumps(summary, indent=2))
print("SUMMARY", json.dumps(summary))
PY

# (optional) post a small Discord line if your webhook is available on the Pi
WEBHOOK="$(grep -s '^DISCORD_WEBHOOK_URL=' pi-app/.env | cut -d= -f2- || true)"
if [[ -n "${WEBHOOK}" ]]; then
  LINE="$(python3 - <<'PY'
import json, glob
p = sorted(glob.glob(".agent/sampler/summary-*.json"))[-1]
s = json.load(open(p))
print(f"Sampler: kept {s['kept']} (dedup {s['dedup']}, errs {s['errs']}) from {s['manifest']}")
PY
)"
  curl -fsS -H 'Content-Type: application/json' \
    -d "{\"content\":\"${LINE}\"}" "$WEBHOOK" >/dev/null || true
fi
