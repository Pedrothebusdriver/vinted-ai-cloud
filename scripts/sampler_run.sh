#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
OUT="$ROOT/data/online-samples/$(date -u +%Y-%m-%d)"
mkdir -p "$OUT"
echo "sampler stub ran at $(date -u +%FT%TZ)" >> "$OUT/_stub.txt"
jq -n --arg ts "$(date -u +%FT%TZ)" '{ok:true, ts:$ts, fetched:0, kept:0}' > "$OUT/report.json" 2>/dev/null || \
  printf '{"ok":true,"ts":"%s","fetched":0,"kept":0}\n' "$(date -u +%FT%TZ)" > "$OUT/report.json"
echo "OK"
