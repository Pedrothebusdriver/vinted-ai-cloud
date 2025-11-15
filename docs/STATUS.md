# Project Status & Context

_Last updated: 2025-11-12 (late night)_

## High-level Overview
- **Uploader (Pi)** – FastAPI app (`pi-app/app/main.py`) handles phone uploads, converts/optimises photos, runs OCR/classification, auto-builds drafts, and now enforces compliance (faces/people/min-size) before saving.
- **Cloud helper** – Flask service (`app.py` or rendered deployment) scrapes Vinted for comps; COMPS requests use `/api/price`.
- **Sampler + eval loop** – `scripts/run_sampler_cycle.sh` downloads sample photos, calls `/api/infer?fast=1`, writes `data/evals/<date>/eval-results.jsonl`, posts per-image eval blurbs to the AI-test webhook, and triggers `/learning` snapshot (general channel).
- **Learning monitor** – `/learning` page + Discord button summarise sampler buckets, eval accuracy, and label-learning history.

## Automation & Scheduling
- `scripts/systemd/vinted-sampler.timer` runs the cycle every 30 minutes between **21:00–06:00** (plus a 06:00 run). Manage via:
  ```bash
  systemctl --user status vinted-sampler.timer
  systemctl --user start vinted-sampler.service   # manual run
  journalctl --user -u vinted-sampler.service -f  # live logs
  ```
- Logs are in `pi-app/var/sampler.log`.

## Discord Webhooks
- `DISCORD_WEBHOOK_DRAFTS` (aka Vinted bot) – draft-ready posts with thumbnail previews.
- `DISCORD_WEBHOOK_GENERAL` – learning snapshot (3 thumbs + stats).
- `DISCORD_WEBHOOK_AI_TEST` – per-image eval blurbs, errors, and tuning notes.
- `DISCORD_WEBHOOK_ALERTS` – compliance rejections (faces/people/min-size).
- `DISCORD_WEBHOOK_URL` – legacy/default hook used as fallback when others are unset.
- `PUBLIC_BASE_URL` – public host (e.g., `http://100.85.116.21:8080`) used when generating draft links; set it so Discord links open directly.

## Compliance Guard
- Located at `pi-app/app/compliance.py`.
- Checks min dimension (default 240 px), file size, blur (Laplacian variance), large faces, and full-body detections via OpenCV HOG.
- Uploads/sampler images failing the check are deleted, alerts posted, and drafts marked `rejected`.

## Latest Progress (Nov 12)
- **Metadata-aware uploads** – `/api/upload` accepts an optional `metadata` form field; payloads are stored under `data/ingest-meta` and consumed by `_process_item` as fallback brand/size/type hints.
- **Slug-based brand/size fallback** – when OCR is blank, we now parse Vinted-style slugs (file names, ids, terms) to guess the brand via RapidFuzz and sizes via regex, so drafts no longer stay empty.
- **Sampler hygiene** – `tools/vinted_sampler.py` drops zero-byte downloads and ships metadata during uploads so Pi-side drafts mirror the original listing context.
- **Discord routing** – draft posts (with thumbnails + public links) go to `DISCORD_WEBHOOK_DRAFTS`, AI-test blurbs to `DISCORD_WEBHOOK_AI_TEST`, learning snapshots to `DISCORD_WEBHOOK_GENERAL`, and compliance hits to `DISCORD_WEBHOOK_ALERTS`.
- **Vinted credentials staged** – throwaway account stored at `~/secrets/vinted.json` (Pi) for authenticated sampler work.
- **Discord bridge bot** – `tools/discord_bridge_bot.py` now mirrors Discord channel chat into `.agent/discord-bridge/inbox` (attachments optional) and relays CLI replies from `.agent/discord-bridge/outbox`, with an optional webhook forwarder and ready-to-use systemd unit.
- **Agent relay bus** – `tools/agent_relay.py` gives Codex agents a shared inbox under `.agent/relay/`, plus `tools/agent_relay_stream.py` for always-on listeners, so the CLI + Discord agents can coordinate (send/pull JSONL messages, optional broadcast/webhook mirroring) without user intervention.
- **Project scope + mobile funnel docs** – Added `docs/PROJECT_SCOPE.md` (product phases) and `docs/iphone-shortcut.md` so every agent shares the same end goal and testers can upload from iPhone via Shortcuts.
- **Manual upload hardening** – `/api/upload` now expects an API key + per-IP rate limit, the web uploader stores the key client-side, and the Shortcut/phone guides were updated alongside a new `docs/manuals/web-upload.md`.
- **Authenticated Vinted sampler** – `tools/vinted_sampler.py` loads OAuth creds from `~/secrets/vinted.json`, caches tokens, enforces optional catalog filters, emits normalized `_summary.json`, and `run_sampler_cycle.sh` switches to it automatically when `SAMPLER_SOURCE=vinted`.
- **Hardware/security playbook** – captured the migration + hardening plan under `docs/hardware_security.md` (hardware shortlist, provisioning script outline, firewall + secret storage checklist).
- **Architecture deep dive** – `docs/deep_dive.md` captures the current stack, pain points, upgrade plan, and hardware migration options (Pi → mini PC/Jetson) so we can chip away at refactors without losing context.
- **Tooling + heartbeat automation** – `pyproject.toml` + `requirements-dev.txt` add ruff/mypy/pytest scaffolding (`scripts/check.sh` runs the suite), `.env.example` now ships sanitized placeholders, and `tools/heartbeat_ping.py` + `agent-heartbeat.timer` keep `.agent/agent-heartbeat.txt` fresh without manual commands.
- **Sampler instrumentation** – `tools/vinted_sampler.py` can now route through `cloudscraper`, primes the base URL, and writes failing responses/CF challenges to `.tmp/vinted-auth/` (`--trace-dir`), giving the authenticated-sampler work a tighter feedback loop.
- **Observability baseline** – Prometheus metrics are exposed at `/metrics` (structured logs already active), `pi_items_processed_total` + `pi_learning_posts_total` track core flows, and `observability/docker-compose.yml` ships a ready-to-run Prometheus + Grafana stack with docs under `docs/observability.md`.
- **Event stream** – `app/events.py` now appends JSONL records under `pi-app/data/events/<date>.jsonl` for every processed/rejected item and learning snapshot, so analytics/data-lake tooling can slurp structured history without scraping logs.
- **Quality checks CI** – `.github/workflows/check.yml` now runs ruff, mypy, and pytest on every push/PR with the necessary system deps, keeping GitHub in lockstep with the local `scripts/check.sh`.

### In Progress — Codex
- Harden the new Vinted sampler (CF soak tests + Playwright fallback) and monitor the nightly runs.
- Move into the hardware hardening track (mini PC benchmarks, provisioning scripts, firewall/secrets rollout).

## Open TODO / Roadmap
1. Make the sampler resilient to Cloudflare (headless browser or curated retail feeds) so we consistently harvest non-zero listings.
2. Improve classifier heuristics (colour/type/brand confidence) and measure uplift in `data/evals`.
3. Expand compliance (blur/NSFW heuristics, OCR keyword screening).
4. Deep-dive review + hardware plan (mini PC options, architecture, UX upgrades).
5. Draft polish: richer description templates, condition heuristics, better price hints.
6. Enable always-on agent relay listeners (`tools/agent_relay_stream.py` or `agent-relay@` units) for `codex-cli` + `codex-discord`, then plug the Discord bridge into the same stream once the bot token is ready.

## Handy Commands
```bash
# Run sampler cycle immediately
./scripts/run_sampler_cycle.sh

# Trigger learning snapshot manually
curl -X POST http://127.0.0.1:8080/api/learning/notify

# Test infer endpoint
curl -s -F file=@/path/to/photo.jpg 'http://127.0.0.1:8080/api/infer?fast=1'
```

Use this file as the starting point whenever context is needed; update the TODO list + timestamp after major changes.
