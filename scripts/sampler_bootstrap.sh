#!/usr/bin/env bash
set -euo pipefail
cd ~/vinted-ai-cloud/pi-app
mkdir -p var data/online-samples rules
python3 -m venv .venv >/dev/null 2>&1 || true
. .venv/bin/activate
pip install --upgrade pip >/dev/null
pip install requests pillow imagehash >/dev/null
echo "[OK] sampler bootstrap ready" | tee -a var/sampler.log
