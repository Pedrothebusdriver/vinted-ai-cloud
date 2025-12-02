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

1. Create/activate a venv and install runtime deps:

       python3 -m venv .venv
       source .venv/bin/activate
       python -m pip install -r requirements.txt -r pi-app/requirements.txt

2. Install dev tools (for backend + eval):

       python -m pip install -r requirements-dev.txt

   This pulls in FastAPI/Pydantic dev bits plus pytest/pytest-cov, OpenCV
   and Pillow so the tests and eval CLIs run in the same environment.

3. Run backend tests before pushing:

       pytest tests -q

   You can still run the targeted compliance test alone with:

       pytest tests/test_compliance.py

4. Run mobile checks whenever you touch `mobile/`:

       cd mobile
       npm install
       npm test -- --runTestsByPath src/screens/__tests__/UploadScreen.test.tsx
       npm test -- --runTestsByPath src/screens/__tests__/DraftDetailScreen.test.tsx
       npx tsc --noEmit

   If you change other screens, add more test paths here over time.

5. Document major changes:

   If you add or change anything substantial (new endpoints, new flows,
   new background jobs, mobile UI changes, etc.), you **must** update:

   - "## Current status (YYYY-MM-DD)" with what now exists in the system.
   - "## Next focus (Month YYYY)" if you've changed what Pete should care
     about next.

   Treat the README as the canonical “what exists + what’s next” view for
   both agents and Pete. If it isn't captured here, assume future agents
   won't know it exists.

CI is minimal today; whenever you add additional tests or linting, capture
the commands in this section so every agent can reproduce them locally.

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

Detailed instructions live in `docs/manuals/expo-upload.md`. Highlights:
- Upload screen – select multiple photos from the device and send them (with optional JSON metadata) to `/api/upload`.
- Drafts screen – lists `/api/drafts`, tap to open the existing Pi draft UI.
- Activity screen – shows recent events from the new `/api/events` endpoint.

## Phone uploads (Shortcuts)
- Use `docs/manuals/phone-upload.md` for the tap-by-tap Shortcut flow.
- Expo prototype (above) is the richer UI; both share the same API key + Pi endpoint.

## Current status (2025-12-02)

FlipLens / Vinted AI Cloud is now a full vertical slice from phone → Pi backend → eval/learning, with a half-polished mobile client on top.

**Backend & sampler**

- Python API backend serving:
  - `/health`, `/api/infer`, `/api/upload`, `/api/drafts`, `/api/events`, `/learning`, plus metrics at `/metrics`.
  - Image compliance checks before a draft is created: low-res, face/people violations are deleted and posted to `DISCORD_WEBHOOK_ALERTS`.
- Night sampler + eval loop is wired:
  - `vinted-sampler.timer` calls `scripts/run_sampler_cycle.sh` on a schedule, pulls sample clothing photos, calls `/api/infer?fast=1`, and writes evals to `data/evals/<date>/eval-results.jsonl`.
  - Each run can push a “learning snapshot” and per-image blurbs into Discord for quick review.
- Marketplace eval tooling is live:
  - `tools/marketplace_eval/run_eval.py` runs against stored data and writes Markdown reports under `tools/marketplace_eval/reports/` (latest report is checked in for reference).

**Pi core & services**

- Pi/mini-PC is the primary “core” target:
  - Systemd units for sampler + heartbeat live under `scripts/systemd/` and can be enabled with `systemctl --user ...`.
  - `tools/heartbeat_ping.py` appends pings to `.agent/agent-heartbeat.txt` and can mirror them to a Discord relay via `AGENT_RELAY_WEBHOOK_URL`.
- Observability hooks:
  - Prometheus metrics exposed at `/metrics`.
  - Optional `observability/docker-compose.yml` stack (Prometheus + Grafana) is ready to run locally for dashboards/alerts.

**Discord bridge & agents**

- Discord bridge bot:
  - `tools/discord_bridge_bot.py` listens for messages in configured channels and writes them under `.agent/discord-bridge/inbox/`.
  - `tools/discord_bridge_send.py` posts replies back to Discord from the local filesystem queue.
- Discord docs (`docs/discord_bridge.md`, `docs/discord_channels_review.md`, `docs/discord_guidelines.md`) describe:
  - How the bridge is wired.
  - How channels are meant to be used going forward.
  - Which spaces are for logs, which are for human conversation.

**Mobile (Expo client)**

- Early React Native app in `mobile/`:
  - **Upload screen**: multiple photo selection + send to `/api/upload`, now using shared design tokens for spacing, cards and buttons.
  - **Drafts list**: scrollable card list showing thumbnail strips, brand/size/condition, description, price badge and server info card.
  - **Draft detail**: structured, keyboard-aware form with:
    - Horizontal photo gallery,
    - Condition/status chips,
    - GBP price input with prefix,
    - Sticky action bar for save/post/export.
  - **Connect / server settings**:
    - Shows current backend, exposes “Test connection”, and reflects configuration from `.env` (using `EXPO_PUBLIC_API_BASE` etc.).
- Mobile tests:
  - Jest tests for `UploadScreen` and `DraftDetailScreen` pass.
  - `npx tsc --noEmit` is clean.

**Dev tooling & tests**

- Python:
  - Runtime deps in `requirements.txt` plus new dev bundle in `requirements-dev.txt`:
    - `fastapi`, `pydantic`, `opencv-python`, `pillow`, `pytest`, `pytest-cov`.
  - Backend test suite:
    - `pytest tests -q` passes (only deprecation warnings from FastAPI/Pydantic).
- Frontend:
  - `mobile/` has Jest + TypeScript checks wired as above.
- CLIs:
  - `tools/dev_show_learning_status.py` and `tools/marketplace_eval/run_eval.py` run without crashing in the current setup.

## Next focus (Dec 2025)

Short term, the priority is making the “phone → Pi → listing” loop feel like a product, not a lab demo:

1. **Smooth connection & startup**
   - Harden the mobile “Test connection” flow:
     - Add a real timeout, clear error messages, and always clear the spinner state.
   - On app launch, auto-reuse the last known good backend and drop the user straight into the main flow when the Pi is reachable.

2. **Photo quality & export fidelity**
   - Review how images are resized/compressed for:
     - On-device thumbnails.
     - The content you copy over to Vinted.
   - Adjust resize/compression so exported photos still look sharp enough for real listings.

3. **End-to-end listing UX**
   - Treat one item as the “golden path”:
     - Take photos on the phone.
     - Upload to Pi, generate draft.
     - Confirm brand/size/title/price in the mobile app.
     - Export a ready-to-paste block (title, description, price, tags) that you actually use in Vinted.
   - Capture any manual steps you still have to do and feed those back into the roadmap.

4. **Pi reliability**
   - Make sure core services are running under systemd on the Pi (API + sampler + heartbeat, where needed).
   - Verify:
     - `/health` and `/metrics` are always up when the Pi is “on”.
     - Logs and eval reports are rotating to disk cleanly.

5. **Tighter agent loop**
   - Standardise the dev workflow in this repo so agents always:
     - Create/activate `.venv`.
     - Install `requirements.txt` + `requirements-dev.txt`.
     - Run `pytest`, mobile Jest tests, and `npx tsc --noEmit` before pushing.
   - Keep this section updated whenever new tests or tools are added so agents don’t guess.
