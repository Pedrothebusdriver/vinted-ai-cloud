#!/usr/bin/env bash
set -euo pipefail
cd ~/vinted-ai-cloud/pi-app
. .venv/bin/activate
python - <<'PY'
import json, os, time, pathlib
root = pathlib.Path.cwd()
date = time.strftime("%Y-%m-%d")
out = root/"data/online-samples"/date
out.mkdir(parents=True, exist_ok=True)
log = root/"var/sampler.log"
log.write_text(f"[{time.strftime('%H:%M:%S')}] sampler stub ran -> {out}\n", encoding="utf-8")
print(json.dumps({"ok": True, "out": str(out)}))
PY
