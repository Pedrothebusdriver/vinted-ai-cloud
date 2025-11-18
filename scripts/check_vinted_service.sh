#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="${1:-http://127.0.0.1:8080/health}"

echo "==> systemctl --user status vinted-app.service"
systemctl --user status vinted-app.service --no-pager

echo
echo "==> journalctl --user -u vinted-app.service -n 100"
journalctl --user -u vinted-app.service -n 100 --no-pager

echo
echo "==> curl $HEALTH_URL"
if command -v curl >/dev/null 2>&1; then
  curl -fsS "$HEALTH_URL" || true
else
  echo "curl not installed; skipping health check." >&2
fi
