# Vinted AI Cloud (Pete)

Render-ready Flask API that analyses clothing photos:
- CLIP (FashionCLIP if available) for item type
- EasyOCR + fuzzy match for brand and size (adult + children)
- Returns ready-to-use listing JSON

## Local run
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
# -> http://127.0.0.1:10000/health

## Test
bash ./test_upload.sh

## Automated sampler + eval

Run `./scripts/run_sampler_cycle.sh` to download a batch of sample clothing photos,
infer tags via `/api/infer?fast=1`, write `data/evals/<date>/eval-results.jsonl`,
and push a Discord learning snapshot. Customize behaviour via env vars in
`pi-app/.env`, e.g.:

```
SAMPLER_SOURCE=lorem             # or openverse / vinted (auth required)
SAMPLER_BUCKETS=jackets,jeans
SAMPLER_PER_BUCKET=10
SAMPLER_TOTAL_LIMIT=40
PI_INFER_URL=http://127.0.0.1:8080/api/infer?fast=1
DISCORD_AGENT_WEBHOOK=https://discord.com/api/webhooks/...
```

For real listings, set `SAMPLER_SOURCE=vinted`, drop your creds in
`~/secrets/vinted.json`, and follow the steps in `docs/vinted-auth-notes.md`.

Optional systemd units for the Pi live in `scripts/systemd/`. Copy them to
`~/.config/systemd/user/` and enable the timer for nightly runs:

```
mkdir -p ~/.config/systemd/user
cp scripts/systemd/vinted-sampler.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now vinted-sampler.timer
```

> **Heads up:** `pi-app/.env.example` now ships with placeholder webhooks/tokens. Always copy it to `.env`, fill in your own Discord URLs/secrets, and keep the real file out of git.

## Discord bridge bot

Want to ping Codex from your phone? Deploy the Pi-hosted Discord bridge:

- Run `tools/discord_bridge_bot.py` with `DISCORD_BRIDGE_TOKEN` and `DISCORD_BRIDGE_CHANNELS`.
- Incoming Discord messages are mirrored under `.agent/discord-bridge/inbox/`.
- Queue replies via `tools/discord_bridge_send.py "message"` (they post back to Discord).

See `docs/discord_bridge.md` for full setup notes plus the systemd unit.

## Architecture deep dive

Need the bigger picture (hardware options, refactor plan, sampler/cloud helper roadmap)? See `docs/deep_dive.md` for the full audit + upgrade checklist.

## Development workflow

1. Create a local venv and install runtime deps as usual.
2. Install dev tooling once:
   ```bash
   pip install -r requirements-dev.txt
   ```
3. Run the full lint/type/test suite via `./scripts/check.sh` (creates `.venv` if missing).

Tooling is configured in `pyproject.toml`:
- `ruff` for lint/import sorting
- `mypy` for type checks
- `pytest` (async-enabled) under `tests/`
- GitHub Actions runs `.github/workflows/check.yml` on every push/PR so CI mirrors the local checks automatically.

## Automated heartbeat

Use `tools/heartbeat_ping.py` to append UTC entries to `.agent/agent-heartbeat.txt` and mirror them to the Discord relay (uses `AGENT_RELAY_WEBHOOK_URL`). Enable the bundled systemd timer on the Pi/mini PC to keep pings fresh:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/systemd/agent-heartbeat.* ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agent-heartbeat.timer
```

Override the service with a drop-in if you need a different cadence or message.

## Observability

- Metrics: FastAPI now exposes Prometheus metrics at `/metrics` (enabled automatically on startup). Custom counters track processed drafts (`pi_items_processed_total`) and learning posts.
- Local stack: `observability/docker-compose.yml` spins up Prometheus (9090) + Grafana (3000). Update `observability/prometheus.yml` with your Pi/mini-PC IP if `host.docker.internal` isn’t available, then run `docker compose up -d` inside `observability/`.
- Dashboards: point Grafana at Prometheus (`http://prometheus:9090`) and import any FastAPI/Prom dashboards; add alerts for sampler failures or heartbeat gaps as needed.
- Event log: every processed/rejected item plus learning snapshot now writes to `pi-app/data/events/<date>.jsonl`, which you can stream into DuckDB/Parquet or your analytics stack.

## Mobile prototype (Expo)

Early React Native client lives in `mobile/` (Expo). To run it locally:

```bash
cd mobile
cp .env.example .env            # set EXPO_PUBLIC_API_BASE/PUBLIC_BASE
npm install
npm run ios    # or npm run android / npm run web
```

Features so far:
- Upload screen – select multiple photos from the device and send them (with optional JSON metadata) to `/api/upload`.
- Drafts screen – lists `/api/drafts`, tap to open the existing Pi draft UI.
- Activity screen – shows recent events from the new `/api/events` endpoint.

## Current status (2025-11-11)

- **Image compliance** – every uploaded or sampled photo is checked (`app/compliance.py`) for minimum resolution and visible people/faces before the draft is created; violations are deleted immediately and posted to `DISCORD_WEBHOOK_ALERTS`.
- **Sampler cadence** – `vinted-sampler.timer` runs `run_sampler_cycle.sh` every 30 minutes from 21:00–06:00, downloading ~60 clothing shots per cycle, running `/api/infer?fast=1`, logging results under `data/evals/<date>`, and pushing both per-image eval blurbs (fails highlighted) plus a learning snapshot to Discord.
- **Draft quality** – new drafts automatically get Vinted-friendly titles (brand + colour + item + size), default condition (“Good”), and sanitized attributes; `Check Price` continues to hit the Flask cloud helper for comps.
- **Learning dashboard** – visit `/learning` on the Pi to see sampler buckets, eval accuracy, and recently learned label text, plus a “Share snapshot to Discord” button for manual updates.
