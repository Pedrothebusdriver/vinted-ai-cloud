#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${1:-$HOME/vinted-ai-cloud}"
APP_DIR="$REPO_ROOT/pi-app"

echo "==> Using repo: $REPO_ROOT"
cd "$REPO_ROOT"

echo "==> Pulling latest Git changes..."
git pull --ff-only

echo "==> Ensuring root-level Python deps..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "==> Ensuring Pi app venv + deps..."
python3 -m venv "$APP_DIR/.venv"
source "$APP_DIR/.venv/bin/activate"
pip install --upgrade pip
pip install -r "$APP_DIR/requirements.txt"

echo "==> Running SQLite migration helper..."
python "$REPO_ROOT/scripts/sqlite_migrate.py" --db "$APP_DIR/data/vinted.db"
deactivate

echo "==> Reloading systemd unit..."
systemctl --user daemon-reload
systemctl --user restart vinted-app.service

echo "==> Deploy complete. Run scripts/check_vinted_service.sh to verify status."
