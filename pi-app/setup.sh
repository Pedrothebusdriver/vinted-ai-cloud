#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"

echo "==> Installing system packages..."
sudo apt update
sudo apt install -y python3-venv python3-pip tesseract-ocr libtesseract-dev libgl1 libglib2.0-0 chromium fonts-dejavu-core

echo "==> Creating Python venv and installing requirements..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Initialising database..."
python - <<'PY'
from app.db import init_db
init_db()
print("DB initialised")
PY

[ -f .env ] || cp .env.example .env

echo "==> Creating systemd user service..."
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/vinted-app.service" <<UNIT
[Unit]
Description=Vinted Pi MVP (FastAPI)
After=network.target

[Service]
Type=simple
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure

[Install]
WantedBy=default.target
UNIT

systemctl --user daemon-reload
systemctl --user enable vinted-app.service
systemctl --user restart vinted-app.service

echo
echo "✅ Setup complete. Next: edit $APP_DIR/.env with your Discord webhook and COMPS_BASE_URL, then restart the service."
