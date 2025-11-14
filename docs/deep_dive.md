# Deep Dive – Vinted AI Cloud (Nov 2025)

## 1. Current Architecture Snapshot

| Layer | Components | Notes |
| --- | --- | --- |
| Phone → Pi uploader | FastAPI app in `pi-app/app/main.py` (monolithic). Handles uploads, image conversion, OCR, compliance, metadata heuristics, DB writes, Discord alerts, `/learning` UI, `/api/infer`. | Heavy background task inside FastAPI event loop; single semaphore throttles conversion on Pi 3/4. |
| Draft data | SQLite (`pi-app/app/db.py`) with tables for items/photos/attributes/drafts/prices/comps. | No FKs/indexes; retention relies on manual cleanup; no migrations. |
| Cloud helper | Flask (`app.py`, `Dockerfile.helper`). Scrapes Vinted via JSON endpoints + HTML fallback. | Stateless, but Cloudflare easily blocks; no login; caching only in-memory. |
| Sampler/eval automation | `scripts/run_sampler_cycle.sh` → `tools/sampler.py` (OpenVerse placeholders) + `tools/eval_report.py` + `/api/learning/notify`. Systemd timer runs nightly. | Vinted sampler (`tools/vinted_sampler.py`) not yet integrated; no retry/backoff/alerting. |
| Discord + relay | Multiple webhooks for drafts/evals/learning/compliance. New bridge (`tools/discord_bridge_bot.py`) and relay (`tools/agent_relay*.py`) exist but not yet in production. | No auth, no message dedupe; relies on manual start until systemd units enabled. |
| Observability | `pi-app/var/sampler.log`, Discord pings, `.agent/agent-heartbeat.txt`. | No central logging or metrics. |

## 2. Key Pain Points

1. **Monolithic Pi app** – 1k+ lines mixing OCR, pricing, orchestration, HTTP routes. Hard to test, no retry queue, failures require manual intervention.
2. **Legacy heuristics** – Colour/type detection and OCR rely on simple thresholds/regex; accuracy limited compared to CLIP/FashionCLIP + modern OCR.
3. **Compliance gaps** – Haar/HOG detectors miss partial people and misfire on patterned garments; duplicate imports, minimal logging.
4. **Sampler fragility** – Still scraping without login, so Cloudflare or zero results break nightly runs; metadata flow incomplete.
5. **Tooling/observability** – No tests, linting, metrics, or health checks; `.env.example` leaks a real webhook URL; heartbeat manual.
6. **Hardware constraints** – Pi throttles conversions and OCR; migrating to mini PC (Intel N100/N305 or Ryzen 7 mini) or Jetson is planned but undocumented.

## 3. Upgrade Proposals

### 3.1 Pi Service Refactor

1. Extract modules:
   - `app/services/ingest.py` – file handling, conversion, background queue stub.
   - `app/services/vision.py` – OCR, CLIP/FashionCLIP integration, dominant colour via histogram.
   - `app/services/pricing.py` – comps & caching, bridging to cloud helper or local fallback.
   - `app/services/notify.py` – Discord + relay notifications.
2. Introduce a persistent job queue (Redis + RQ or Celery) so uploads survive restarts. FastAPI enqueues jobs; worker handles OCR/compliance/pricing.
3. Add structured logging (e.g., `structlog`), request IDs, and Prometheus-friendly counters. `/health` should report worker queue depth.

### 3.2 Vision/Compliance Upgrades

- Replace OCR with PaddleOCR (CPU-friendly) or TrOCR ONNX; keep fallback to Tesseract.
- Integrate CLIP embeddings (use FashionCLIP weights) for `item_type` + `colour` classification; persist embeddings for future fine-tuning.
- Swap compliance detection to an ONNX person/NSFW detector (e.g., `yolov8n-pose` or `nsfw_detector`) and add Exif-aware dimension checks.
- Expand learning table: store precision/recall on label hashes, surface accuracy in `/learning`.

### 3.3 Sampler & Cloud Helper

- Finish authenticated Vinted sampler:
  - Load cookies/credentials from `~/secrets/vinted.json`.
  - Use mobile GraphQL endpoints (or Playwright) to avoid Cloudflare.
  - Store normalized metadata JSON alongside images.
  - Integrate with `scripts/run_sampler_cycle.sh` via `SAMPLER_SOURCE=vinted`.
- Harden `app.py`:
  - Session reuse, randomized UAs, and fallback to headless browser.
  - Disk cache with TTL + compression; store sample responses for offline training.
  - Alert when zero comps returned.

### 3.4 Tooling & Observability

- Add `pyproject.toml` with shared deps, `ruff`, `mypy`, and `pytest`.
- Move secrets to `pi-app/.env` template with placeholders; document `~/secrets/*.env`.
- Stand up Loki/Promtail or at least central journald shipping; add `scripts/monitor/` for system health checks.
- Automate heartbeat: cron/systemd writes to `.agent/agent-heartbeat.txt` every 5 min.
- Use `AGENT_RELAY_WEBHOOK_URL` + `agent-relay@` services to keep agent chatter synced automatically.

### 3.5 Hardware Migration Plan

| Option | Pros | Cons | Notes |
| --- | --- | --- | --- |
| Intel N100/16 GB mini PC | Cheap (£200-250), low power, supports Docker & CLIP CPU | No GPU acceleration | Run FastAPI + queue + cloud helper; Pi handles uploads only. |
| Ryzen 7 7840HS mini PC | High CPU+GPU, can run ONNX/TensorRT | Higher cost (~£600) | Future-proof for FashionCLIP + NSFW models. |
| Jetson Orin Nano | Native GPU inference | Limited general-purpose performance | Best if we invest heavily in CV inference locally. |

See `docs/hardware_security.md` for the detailed hardware shortlist, benchmark
plan, provisioning flow, and firewall/secrets checklist.

Migration steps:
1. Snapshot `pi-app/data` to external SSD.
2. Provision mini PC with Ubuntu/Proxmox; install Docker + Compose.
3. Deploy Pi app + cloud helper containers; mount shared storage.
4. Update `PUBLIC_BASE_URL` + DNS, keep Pi as thin uploader/gateway.

### 3.6 Documentation & UX

- Produce a “Runbook” covering setup, failure scenarios, systemd services, heartbeat monitoring, and relay usage.
- Expand `/learning` dashboard with queue depth, sampler stats, and last heartbeat.
- Document hardware topology, security (firewall, VPN), and user flows for phone uploads + Discord interactions.

## 4. Priority Stack (Nov 13)

1. **Sampler authentication + scraping resilience** – unblock real data flow (Cloudflare-safe client, Playwright fallback, metadata parity) so all downstream metrics are meaningful.
2. **Observability foundation** – structured logs (done) + Prometheus metrics + Loki/Promtail shipping + Grafana dashboards + alerting hooks.
3. **Pi service modularisation + work queue** – extract ingest/vision/pricing/notify modules and introduce Redis/RQ (or Celery) workers so uploads survive restarts and scale beyond Pi.
4. **Vision/compliance upgrades** – drop heuristics in favour of CLIP/FashionCLIP + PaddleOCR/ONNX models and NSFW/body detectors; wire results into learning DB with precision/recall tracking.
5. **Reviewer UX + collaboration** – lightweight React/Streamlit front-end for approving drafts, overriding attributes, and feeding corrections back into the learning tables; add auth (Auth0/Supabase).
6. **Data lake + analytics** – stream sampler/draft events into Parquet/DuckDB (or managed warehouse), build Metabase dashboards, and expose KPIs/SLOs via `/learning`.
7. **Hardware migration + fleet scripts** – codify mini PC builds (Ansible + Docker), add Pi-to-mini cutover playbooks, and plan for a fleet of edge nodes with zero-trust tunnels.
8. **Productisation** – package as SaaS/agent: multi-market connectors, billing/quotas, marketplace-specific compliance, and marketplace-specific templates.

We’ll tackle these in order; as each milestone lands, bubble it up to `docs/STATUS.md` and keep this list current.

## 5. Immediate Action Items

1. **Sampler auth** – build + test logged-in Vinted fetcher, switch nightly timer.
2. **Manual upload funnel (new agent)** – expose `/api/upload` safely (API key/rate limit), publish a web/iOS Shortcut guide so testers can push existing photos without the prototype.
3. **Observability** – add Prometheus metrics + Loki/Promtail scaffolding + dashboard docs.
4. **Bridge automation** – enable Discord bridge service + relay streamers once bot token is available.
5. **Hardware PoC / security hardening (new agent)** – benchmark mini PC options, script provisioning (Ansible/Docker), lock down firewall/secrets, and document the migration path.

Track progress by updating `docs/STATUS.md` and referencing this deep-dive checklist after each milestone.***
