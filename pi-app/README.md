# Vinted Pi – Uploader + Draft Builder (MVP)

Phone uploader → image optimise → label OCR (brand/size) → draft with confidence badges → Discord ping → “Check Price” (Cloud Helper) → review.

## Quick start on the Pi
```bash
git clone https://github.com/Pedrothebusdriver/vinted-ai-cloud.git
cd vinted-ai-cloud/pi-app
bash setup.sh
cp .env.example .env && nano .env   # add DISCORD_WEBHOOK_URL and COMPS_BASE_URL
systemctl --user restart vinted-app.service
