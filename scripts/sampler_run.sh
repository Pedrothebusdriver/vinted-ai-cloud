#!/usr/bin/env bash
set -euo pipefail

# Build a manifest from local training data and optionally run evals.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

OUT_PATH=${MANIFEST_OUT:-}
if [ -z "$OUT_PATH" ]; then
  OUT_PATH=".agent/sampler/manifest-$(date -u +%Y%m%dT%H%M%SZ).json"
fi

python3 tools/build_eval_manifest.py --out "$OUT_PATH"

if [ "${SKIP_EVAL:-0}" != "1" ]; then
  export EVAL_MANIFEST="$OUT_PATH"
  python3 tools/eval_report.py
fi
