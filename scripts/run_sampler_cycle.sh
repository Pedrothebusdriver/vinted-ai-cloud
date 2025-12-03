#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

# Load Pi env defaults if present
if [[ -f "pi-app/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source pi-app/.env
  set +a
fi

# Prefer Vinted when creds are available, otherwise default to Openverse.
if [[ -z "${SAMPLER_SOURCE:-}" ]]; then
  if [[ -f "$HOME/secrets/vinted.json" ]]; then
    SAMPLER_SOURCE="vinted"
  else
    SAMPLER_SOURCE="openverse"
  fi
fi

PI_INFER_URL="${PI_INFER_URL:-http://127.0.0.1:10000/api/infer?fast=1}"
export SAMPLER_SOURCE PI_INFER_URL

LOG_PATH="pi-app/var/sampler.log"
mkdir -p "$(dirname "$LOG_PATH")"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] sampler source=$SAMPLER_SOURCE buckets=${SAMPLER_BUCKETS:-} per=${SAMPLER_PER_BUCKET:-} total=${SAMPLER_TOTAL_LIMIT:-} infer=$PI_INFER_URL" | tee -a "$LOG_PATH"

python3 tools/sampler.py | tee -a "$LOG_PATH"

# Run evals if configured (uses latest manifest by default)
python3 tools/eval_report.py | tee -a "$LOG_PATH"

infer_base="${PI_INFER_URL%%/api/*}"
notify_url="${LEARNING_NOTIFY_URL:-${infer_base}/api/learning/notify}"

curl -s -X POST "$notify_url" -H "Content-Type: application/json" -d '{"ok":true,"source":"sampler"}' >>"$LOG_PATH" 2>&1 || true
