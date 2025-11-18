# Actions for Pete – FlipLens MVP

Single backlog for FlipLens. Each agent reads this file on startup, grabs the next open task for their role, and updates the checklist as work lands.

---

## 0. Ground rules

- FlipLens v1 = **assistant for home Vinted sellers** (not Vinted Pro yet).
- Engine stays on the **Raspberry Pi** for MVP (mini PC later).
- We generate drafts + helper text; no automated posting to Vinted during MVP.
- Multi-agent / Discord relay automations remain paused until FlipLens core + mobile are working end-to-end.

---

## 1. Setup & completed checkpoints

- [x] PRD lives at `docs/fliplens_prd.md` (updated 17 Nov).
- [x] Pi FastAPI already exposes `GET /health` with status + git version (`pi-app/app/main.py`).
- [x] Expo app scaffolded under `mobile/` with Connect, Draft list, and Upload screens hitting `/health`, `/api/drafts`, and `/api/upload`.

---

## 2. Core Engine Agent – Milestone 1 (Vinted AI Core)

**Current reality:** All ingest/price/category logic still sits inside `pi-app/app/main.py`; there is no `app/core/*` package yet, `/api/drafts` only lists existing items, and SQLite still uses the old `attributes` table.

### 2.1 Core module extraction

- [x] Create `pi-app/app/core/models.py` (Pydantic or dataclasses) for `Draft`, `DraftPhoto`, `PriceEstimate`, and `CategorySuggestion` so ingest + API code share typed payloads.
- [x] Check in `data/vinted_categories.json` (plus a short note or fetch helper) containing the category tree we’ll use for suggestions.
- [x] Implement `pi-app/app/core/category_suggester.py` with `suggest_categories(hint_text, ocr_text, filename)` that loads the JSON once, uses keywords + RapidFuzz, and returns the top ranked categories (write pytest coverage).
- [x] Implement `pi-app/app/core/pricing.py` that wraps the current COMPS helper, clamps prices between the env min/max, caches results by `(brand, category_id, size, condition)`, and exposes `suggest_price(...) -> {low, mid, high}`.
- [ ] Extract `_process_item` logic into `pi-app/app/core/ingest.py`: convert + optimise photos, run compliance + OCR, fill brand/size/colour/type, call category/pricing helpers, and return a `Draft` model with ordered `DraftPhoto`s.
- [ ] Update `/api/upload` to become a thin shim that calls `core.ingest.build_draft(...)` so new endpoints can reuse the same code path while the legacy Shortcut keeps working.

### 2.2 Draft API surface

- [ ] Add request/response schemas (e.g., `pi-app/app/api/schemas.py`) for the draft endpoints so FastAPI returns the same structure everywhere.
- [ ] Implement `POST /api/drafts` (multipart images + optional JSON metadata) that calls `core.ingest`, saves rows via the new schema, honors upload auth/rate limits, and returns the newly created `Draft`.
- [ ] Implement `GET /api/drafts/{draft_id}` returning full draft metadata (photos, attributes, price ranges, compliance flags) pulled from SQLite.
- [ ] Implement `PUT /api/drafts/{draft_id}` allowing the mobile app to update title, description, category_id, status, and `selected_price`, updating `updated_at`.
- [ ] Expand `GET /api/drafts` to read from the new `drafts` table, include thumbnails + status + price ranges, and accept `?status=` filters for mobile (drop the legacy `attributes` blob once the new response ships).
- [ ] Expose `POST /api/price` (or upgrade the existing helper) to call `core.pricing.suggest_price` so Pi UI + mobile can re-run pricing on demand.

### 2.3 Database + Pi UI alignment

- [ ] Update `pi-app/app/db.py` schema + helper functions to use the FlipLens `drafts` columns and `photos.draft_id/file_path/position`, phasing out the `attributes` table for brand/size/colour.
- [ ] Run persistence through the new schema: `_process_item`, `/api/upload`, and upcoming `/api/drafts` should only write to `drafts`/`photos`, not `attributes`.
- [ ] Refresh the Pi templates (`pi-app/templates/index.html`, `draft.html`) to read brand/size/colour/prices from the new columns and show status badges (Draft vs Ready).
- [ ] Wire the existing `scripts/sqlite_migrate.py` helper into a CLI or startup hook so new deployments automatically migrate the DB before serving traffic.

### 2.4 Tests + docs

- [ ] Add pytest coverage for `core.category_suggester`, `core.pricing`, and `core.ingest` (mock OCR/compliance where needed).
- [ ] Add FastAPI integration tests under `pi-app/tests/test_drafts_api.py` that spin up an in-memory SQLite DB and exercise `POST/GET/PUT /api/drafts`.
- [ ] Update `README.md` + `docs/fliplens_prd.md` with request/response examples for `/api/drafts` once the endpoints ship, and remove stale references to the `attributes` table.

---

## 3. Mobile Agent – Milestone 2 (Expo client)

**Current reality:** Connect + Draft list screens run, but the base URL is not persisted, uploads still call `/api/upload`, there is no Draft detail/editor, and there is no “Post to Vinted” helper yet.

### 3.1 Connection + state

- [x] Connect screen hits `/health` and stores the URL in context (Nov 17).
- [x] Persist the server URL (and upload key placeholder) to `AsyncStorage` inside `ServerProvider`, hydrating it on launch (Nov 18).
- [ ] Add an optional Upload Key input on the Connect screen and include it in every API request’s `X-Upload-Key` header (reuse for `/api/drafts` once auth is enforced).

### 3.2 Draft experience

- [x] Create `DraftDetailScreen` that loads a single draft via `GET /api/drafts/{id}`, displays thumbnails + metadata, and surfaces editable fields (title, description, price, status). Placeholder data shown if backend not ready (Nov 18).
- [x] Wire `DraftDetailScreen` edits to `PUT /api/drafts/{id}` with optimistic UI feedback (stubs until backend ships).
- [ ] Update `DraftListScreen` to render thumbnails (once API returns URLs), show status chips (Draft/Ready), and add a simple filter/toggle for each list.

### 3.3 Upload + post helper

- [x] Basic Upload screen selects/takes photos and POSTs to `/api/upload` with optional metadata JSON.
- [ ] Switch the Upload screen to call the new `POST /api/drafts` endpoint (reuse the stored upload key/header) once the backend exposes it.
- [ ] Replace the raw metadata textarea with simple inputs (brand, size, condition dropdowns) that compose JSON for the backend.
- [ ] After upload, show a success state that deep-links to the new draft (navigate to `DraftDetailScreen`).
- [ ] Add a “Post to Vinted” helper button on `DraftDetailScreen`: copy title/description/price to the clipboard and open the Vinted app (or instructions) so Pete can publish quickly.

---

## 4. Ops Agent – Deployment + migrations

**Current reality:** `pi-app/setup.sh` writes the systemd unit via heredoc, the SQLite migration helper exists but isn’t part of the deploy flow, and there’s no single doc describing how to upgrade/restart the Pi service for FlipLens.

### 4.1 Service + scripts

- [x] Check `vinted-app.service` into git under `scripts/systemd/` (and update `pi-app/setup.sh` to copy it) so future changes are tracked in the repo. **(2025-11-17 – unit now lives in `scripts/systemd/` and setup copies it.)**
- [x] Add a helper script (e.g., `scripts/check_vinted_service.sh`) that runs `systemctl --user status vinted-app`, tails the last 100 journal lines, and curls `/health` for quick smoke tests. **(2025-11-17 – script prints status, last 100 logs, and hits `/health`.)**
- [x] Create a lightweight `scripts/pi/deploy_fliplens.sh` that pulls git, installs requirements, runs migrations, and restarts the systemd unit to avoid hand-written commands each time. **(2025-11-17 – deploy script pulls main, refreshes venvs, runs `scripts/sqlite_migrate.py`, and restarts the unit.)**

### 4.2 Database rollout

- [ ] Add `scripts/backup_sqlite.sh` (or similar) that tars `pi-app/data/vinted.db` with a timestamp before migrations; document where backups live.
- [ ] Once the core schema changes merge, run `python scripts/sqlite_migrate.py --db ~/vinted-ai-cloud/pi-app/data/vinted.db` on the Pi and log completion (date + SHA) in `.agent/relay` plus this doc.
- [ ] Update `pi-app/setup.sh` (or the new deploy script) to call `scripts/sqlite_migrate.py` automatically so fresh installs and upgrades don’t skip the FlipLens schema.

### 4.3 Monitoring + docs

- [ ] Create `docs/manuals/pi-deploy.md` covering: pulling latest, backing up SQLite, running the migration helper, restarting `vinted-app.service`, and verifying `/health` + `/api/drafts`.
- [ ] Update `pi-app/.env.example` once new Draft APIs introduce additional secrets (e.g., dedicated upload key, mobile auth toggle) so operators know what to fill.
- [ ] Update `docs/manuals/expo-upload.md` (or add a new mobile hand-off doc) describing how to grab the Pi URL/upload key, scan the Expo QR, and run the new Draft editor workflow end-to-end.

---

## 5. Parking lot (not for MVP)

- Discord bridge + `tools/agent_relay.py` multi-agent orchestration.
- Automated Vinted posting via bots/headless browsers.
- Vinted Pro API integration (business accounts).
- Non-clothing categories needing special handling (electronics, toys, etc.).
- CharityLoop client app / broader marketplace integrations.
