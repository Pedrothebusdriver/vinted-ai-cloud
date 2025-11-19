# Actions for Pete – FlipLens MVP

Single backlog for FlipLens. Each agent reads this file on startup, grabs the next open task for their role, and updates the checklist as work lands.

---

## 0. Ground rules

- FlipLens v1 = **assistant for home Vinted sellers** (not Vinted Pro yet).
- Engine stays on the **Raspberry Pi** for MVP (mini PC later).
- We generate drafts + helper text; no automated posting to Vinted during MVP.
- Multi-agent / Discord relay automations remain paused until FlipLens core + mobile are working end-to-end.
- Every agent must start by re-reading the shared docs (PRD, Actions, AGENTS, AGENT_RULES) and then pick the next unchecked `[ ]` task that matches their primary role. If their section has fewer than three open items, they may temporarily help another role after explicitly stating which hat they’re wearing. If their section becomes empty, they must propose 2–3 new tasks (with IDs and checkboxes) aligned with the PRD and append them here before ending the session.

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
- [x] Extract `_process_item` logic into `pi-app/app/core/ingest.py`: convert + optimise photos, run compliance + OCR, fill brand/size/colour/type, call category/pricing helpers, and return a `Draft` model with ordered `DraftPhoto`s.
- [x] Update `/api/upload` to become a thin shim that calls `core.ingest.build_draft(...)` so new endpoints can reuse the same code path while the legacy Shortcut keeps working.
- [ ] M1-01 – Document every ingest stage (`convert`, `ocr`, `pricing`) with docstrings and comments in `pi-app/app/core/ingest.py` so future contributors know where to plug in logic.
- [ ] M1-02 – Move `_preprocess_for_ocr` from `main.py` into `core/ingest.py` and adjust imports so tests can use it without FastAPI.
- [ ] M1-03 – Create a small logging helper inside `core/ingest.py` (or `core/logging.py`) that standardises structured logs for item IDs and rejection reasons.
- [ ] M1-04 – Add retry/backoff logic around `ocr.read_text` failures, capturing errors via `events.record_event`.
- [ ] M1-05 – Normalize incoming metadata with a new `sanitize_metadata` function that strips blanks and lowercases expected keys before ingest uses them.
- [ ] M1-06 – Extract colour detection into a dedicated helper returning both the hex value and human label; write at least two unit tests using sample images.
- [ ] M1-07 – Add dependency-injection hooks so ingest functions accept optional compliance/OCR implementations, making tests easier.
- [ ] M1-08 – Persist the photo filename that produced the best OCR result into `draft.metadata` and store it inside the DB for debugging.
- [ ] M1-09 – Detect duplicate photos (perceptual hash) during ingest and auto-drop duplicates before compliance/OCR.
- [ ] M1-10 – Encapsulate `learned_labels` lookups + writes in a helper within `core/ingest.py` and add docstrings for future ML tweaks.
- [ ] M1-11 – Emit Prometheus timing metrics for each ingest stage (conversion, compliance, OCR, pricing) using a helper file.
- [ ] M1-12 – Refactor `_process_item` in `main.py` to become a lightweight wrapper that simply calls `core.ingest.build_draft(...)` and `_store_ingest_result`.

### 2.2 Draft API surface

- [x] Add request/response schemas (e.g., `pi-app/app/api/schemas.py`) for the draft endpoints so FastAPI returns the same structure everywhere.
- [x] Implement `POST /api/drafts` (multipart images + optional JSON metadata) that calls `core.ingest`, saves rows via the new schema, honors upload auth/rate limits, and returns the newly created `Draft`.
- [x] Implement `GET /api/drafts/{draft_id}` returning full draft metadata (photos, attributes, price ranges, compliance flags) pulled from SQLite.
- [x] Implement `PUT /api/drafts/{draft_id}` allowing the mobile app to update title, description, category_id, status, and `selected_price`, updating `updated_at`.
- [x] Expand `GET /api/drafts` to read from the new `drafts` table, include thumbnails + status + price ranges, and accept `?status=` filters for mobile (drop the legacy `attributes` blob once the new response ships).
- [x] Expose `POST /api/price` (or upgrade the existing helper) to call `core.pricing.suggest_price` so Pi UI + mobile can re-run pricing on demand.
- [ ] M1-13 – Add pagination parameters (`limit`, `offset`) to `GET /api/drafts` and cap maximum page size; update tests accordingly.
- [ ] M1-14 – Support filtering drafts by `brand`, `status`, or `item_type` query params with SQL indexes.
- [ ] M1-15 – Return `ETag`/`Last-Modified` headers for drafts so clients can cache them efficiently.
- [ ] M1-16 – Implement `DELETE /api/drafts/{draft_id}` (soft delete) by toggling an `archived_at` column and hiding archived drafts by default.
- [ ] M1-17 – Add `/api/drafts/{id}/photos/{photo_id}` DELETE + PATCH endpoints for removing photos or updating positions.
- [ ] M1-18 – Record ingest queue wait times and expose them via `/api/drafts/{id}` metadata for telemetry.
- [ ] M1-19 – Create `/api/drafts/stats` returning counts by status/brand to fuel future dashboards.
- [ ] M1-20 – Enhance upload auth errors with precise JSON messages and HTTP 429 details when rate limits trip.
- [ ] M1-21 – Allow JSON-only draft creation (no photos) for testing, saving placeholder images to `static/thumbs`.
- [ ] M1-22 – Validate metadata payloads with a Pydantic schema and surface all validation errors in `/api/drafts`.
- [ ] M1-23 – Add `/api/drafts/{id}/history` returning status/price changes stored in a new audit table.
- [ ] M1-24 – Provide `/api/drafts/{id}/export` returning a mobile-friendly summary for copy/paste workflows.

### 2.3 Database + Pi UI alignment

- [ ] Update `pi-app/app/db.py` schema + helper functions to use the FlipLens `drafts` columns and `photos.draft_id/file_path/position`, phasing out the `attributes` table for brand/size/colour.
- [ ] Run persistence through the new schema: `_process_item`, `/api/upload`, and upcoming `/api/drafts` should only write to `drafts`/`photos`, not `attributes`.
- [ ] Refresh the Pi templates (`pi-app/templates/index.html`, `draft.html`) to read brand/size/colour/prices from the new columns and show status badges (Draft vs Ready).
- [ ] Wire the existing `scripts/sqlite_migrate.py` helper into a CLI or startup hook so new deployments automatically migrate the DB before serving traffic.
- [ ] M1-25 – Write a migration script to backfill `drafts.brand/size/colour` columns using existing `attributes` data.
- [ ] M1-26 – Add indexes on `drafts(status)` and `photos(draft_id, position)` to speed up API queries.
- [ ] M1-27 – Update `pi-app/templates/index.html` to highlight drafts with missing required fields (brand/price).
- [ ] M1-28 – Update `pi-app/templates/draft.html` to show low/mid/high prices pulled directly from `drafts`.
- [ ] M1-29 – Remove any remaining `attributes` reads in `main.py` and rely solely on the normalised columns.
- [ ] M1-30 – Implement a schema version table so migrations can check if they’ve already run.
- [ ] M1-31 – Build a maintenance script that cleans up orphaned photos on disk that have no DB rows.
- [ ] M1-32 – Extend `scripts/sqlite_migrate.py` with sanity checks (row counts per table) after migrations run.
- [ ] M1-33 – Document the DB schema (drafts/photos/attributes) in a new `docs/data_model.md` page with diagrams.

### 2.4 Tests + docs

- [ ] Add pytest coverage for `core.category_suggester`, `core.pricing`, and `core.ingest` (mock OCR/compliance where needed).
- [ ] Add FastAPI integration tests under `pi-app/tests/test_drafts_api.py` that spin up an in-memory SQLite DB and exercise `POST/GET/PUT /api/drafts`.
- [ ] Update `README.md` + `docs/fliplens_prd.md` with request/response examples for `/api/drafts` once the endpoints ship, and remove stale references to the `attributes` table.
- [ ] M1-34 – Create `pi-app/tests/test_ingest.py` that mocks OCR/compliance to cover success + rejection branches.
- [ ] M1-35 – Add regression tests for `/api/price` ensuring env min/max clamps are honored.
- [ ] M1-36 – Write a simple load test script (asyncio) to stress `/api/drafts` with concurrent uploads.
- [ ] M1-37 – Document ingest troubleshooting tips in `docs/manuals/ingest.md`.
- [ ] M1-38 – Update the README with a sample `/api/drafts` response so mobile devs have a reference.
- [ ] M1-39 – Extend `pi-app/tests/test_price_api.py` to simulate pricing backend timeouts and ensure graceful fallbacks.
- [ ] M1-40 – Build contract tests comparing `/api/drafts` payloads to the mobile DTO in `mobile/src/api.ts`.
- [ ] M1-41 – Add a “Getting started” doc for AGENT_CORE explaining how to run FastAPI, tests, and linting locally.
- [ ] M1-42 – Introduce a CLI helper in `scripts/cli/list_drafts.py` for debugging without HTTP.
- [ ] M1-43 – Implement env-driven feature flags to toggle experimental ingest behaviour and document them.
- [ ] M1-44 – Refresh `.env.example` with any new variables introduced by the refactor (pricing, feature flags, rate limits).
- [ ] M1-45 – Schedule a cron or script to clean old `INGEST_META` files and update docs about disk hygiene.
- [ ] M1-46 – Create `core/cache.py` to host shared caching utilities for pricing/category lookups.
- [ ] M1-47 – Add tests covering HEIC/RAW conversion using sample fixtures under `tests/fixtures/images`.
- [ ] M1-48 – Ensure the first photo is always the hero image; add tests verifying ordering logic in ingest + DB writes.

---

## 3. Mobile Agent – Milestone 2 (Expo client)

**Current reality:** Connect + Draft list screens run, but the base URL is not persisted, uploads still call `/api/upload`, there is no Draft detail/editor, and there is no “Post to Vinted” helper yet.

### 3.1 Connection + state

- [x] Connect screen hits `/health` and stores the URL in context (Nov 17).
- [x] Persist the server URL (and upload key placeholder) to `AsyncStorage` inside `ServerProvider`, hydrating it on launch (Nov 18).
- [x] Add an optional Upload Key input on the Connect screen and include it in every API request’s `X-Upload-Key` header (2025-11-18 – Connect screen now stores the key and API helper injects `X-Upload-Key`).
- [ ] M2-01 – Add a pull-to-refresh gesture on the Connect screen to quickly re-check `/health`.
- [ ] M2-02 – Build an “App Settings” modal allowing the user to edit base URL + upload key with inline validation.
- [ ] M2-03 – Persist a “last connected” timestamp and show it on the Connect screen.
- [ ] M2-04 – Add support for multiple saved servers (list + select) stored in AsyncStorage.
- [ ] M2-05 – Display the FastAPI version returned by `/health` and warn if it’s outdated vs bundled schema version.

### 3.2 Draft experience

- [x] Create `DraftDetailScreen` that loads a single draft via `GET /api/drafts/{id}`, displays thumbnails + metadata, and surfaces editable fields (title, description, price, status). Placeholder data shown if backend not ready (Nov 18).
- [x] Wire `DraftDetailScreen` edits to `PUT /api/drafts/{id}` with optimistic UI feedback (stubs until backend ships).
- [x] Update `DraftListScreen` to render thumbnails (once API returns URLs), show status chips (Draft/Ready), and add a simple filter/toggle for each list (2025-11-18 – cards now show thumbnail/brand, chips, and filter toggles).
- [ ] M2-06 – Build a price suggestions card that displays low/mid/high and lets the user pick one to set `selected_price`.
- [ ] M2-07 – Add pull-to-refresh on the Draft List + Ready List screens using React Native gesture handlers.
- [ ] M2-08 – Implement pagination/infinite scroll for `/api/drafts` results using the backend’s new limit/offset params.
- [ ] M2-09 – Create skeleton shimmer placeholders while loading drafts to avoid blank jumps.
- [ ] M2-10 – Add a Draft Filters sheet (status, brand, size) and pass the selected filters to the API query string.
- [ ] M2-11 – Display compliance warnings (if provided) on the Draft Detail screen with simple iconography.
- [ ] M2-12 – Implement inline editing for title/description with optimistic updates and rollback on failure.
- [ ] M2-13 – Allow reordering photos via drag-and-drop gestures, posting changes to the backend endpoint.
- [ ] M2-14 – Add the ability to delete a photo from a draft, prompting confirmation before calling DELETE.
- [ ] M2-15 – Show photo metadata (dimensions, label detection) in a collapsible debug panel on Draft Detail.
- [ ] M2-16 – Provide a “Re-check price” button that calls `/api/price` and updates the suggestions UI.
- [ ] M2-17 – Add share sheet support so Pete can export a draft summary via native share dialogs.
- [ ] M2-18 – Cache draft list data offline (AsyncStorage) and hydrate it on app launch before refreshing from the server.
- [ ] M2-19 – Add push-notification scaffolding (Expo Notifications) to alert when a draft finishes processing.
- [ ] M2-20 – Build a connection-status banner that shows when API calls fail and offers retry.
- [ ] M2-21 – Show timestamp for `updated_at` on Draft Detail and list cards.
- [ ] M2-22 – Add local search-as-you-type filter for Draft List while remote filtering is pending.
- [ ] M2-23 – Display `selected_price` vs recommended price to highlight differences.
- [ ] M2-24 – Implement a “Duplicate draft” action that POSTs to a forthcoming backend endpoint.
- [ ] M2-25 – Add analytics logging (even if just console) for key user actions (upload, update, mark ready).
- [ ] M2-26 – Implement dark mode theming toggled via a settings switch.
- [ ] M2-27 – Add a “Mark as posted” control that sets status to posted via PUT `/api/drafts/{id}`.
- [ ] M2-28 – Create a debug screen showing raw API responses for the most recent draft call.
- [ ] M2-29 – Add keyboard-aware scroll handling so inputs are not hidden during editing.
- [ ] M2-30 – Write component-level tests (React Testing Library) for the Draft card + detail form components.

### 3.3 Upload + post helper

- [x] Basic Upload screen selects/takes photos and POSTs to `/api/upload` with optional metadata JSON.
- [ ] Switch the Upload screen to call the new `POST /api/drafts` endpoint (reuse the stored upload key/header) once the backend exposes it.
- [ ] Replace the raw metadata textarea with simple inputs (brand, size, condition dropdowns) that compose JSON for the backend.
- [x] After upload, show a success state that deep-links to the new draft (navigate to `DraftDetailScreen`). (2025-11-18 – Upload screen takes you straight into Draft Detail when the server replies with an `item_id`.)
- [x] Add a “Post to Vinted” helper button on `DraftDetailScreen`: copy title/description/price to the clipboard and open the Vinted app (or instructions) so Pete can publish quickly. (2025-11-18 – helper copies listing text and opens or guides you to the Vinted app.)
- [ ] M2-31 – Add validation/error banners to the Upload screen to surface auth failures or compliance rejection reasons returned by the server.
- [ ] M2-32 – Provide an optional metadata form (brand, size, colour, condition) with dropdowns and validation before upload.
- [ ] M2-33 – Integrate Expo Image Manipulator to downscale large photos before uploading on cellular networks.
- [ ] M2-34 – Cache pending uploads locally (AsyncStorage) so users can resume after an app restart.
- [ ] M2-35 – Build a post-upload summary card listing detected brand/size plus category suggestions.
- [ ] M2-36 – Implement a “Ready to post checklist” highlighting remaining steps (price, description, condition).
- [ ] M2-37 – Add clipboard monitoring to show a toast when FlipLens copies listing text for the user.
- [ ] M2-38 – Surface the backend’s `/api/drafts/{id}/export` payload in the Post Helper once available.
- [ ] M2-39 – Add a “Vinted tips” accordion showing manual notes depending on category/condition.
- [ ] M2-40 – Allow duplicating an existing draft from mobile by selecting it and tapping “Duplicate”.
- [ ] M2-41 – Add a toggle in settings to choose between `/api/upload` legacy flow and new `/api/drafts`.
- [ ] M2-42 – Implement an upload progress indicator per photo (percentage or spinner).
- [ ] M2-43 – Allow multi-select photo removal before submission (e.g., deselect blurry shots).
- [ ] M2-44 – Add instrumentation toggles (log API payloads) hidden behind a long-press gesture for QA.
- [ ] M2-45 – Create Stories/Storybook entries for Upload and Post Helper components to speed up iteration.
- [ ] M2-46 – Add tests for the upload hook/service to ensure it sets headers and handles retries correctly.
- [ ] M2-47 – Build a simple “Support” screen linking to docs/Discord plus mailto for Pete when he reopens support.
- [ ] M2-48 – Embed a short tutorial video or illustrated instructions within the Post Helper screen.
- [ ] M2-49 – Add a bug-report form that gathers API errors/logs and stores them locally for sharing.
- [ ] M2-50 – Implement a “quick actions” widget showing the last uploaded draft for fast access.

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
- [ ] OPS-01 – Create `scripts/pi/backup_sqlite.sh` to copy `pi-app/data/vinted.db` into `backups/` with timestamps and retention notes.
- [ ] OPS-02 – Enhance `scripts/pi/deploy_fliplens.sh` with a post-deploy verification step that curls `/health`, `/api/drafts`, and `/api/price`.
- [ ] OPS-03 – Write `docs/manuals/pi-deploy.md` detailing deploy + rollback including screenshots or terminal snippets.
- [ ] OPS-04 – Add a systemd timer (or cron example) that runs the SQLite backup script nightly; document install steps.
- [ ] OPS-05 – Provide `.env.pi.example` capturing recommended Pi-specific settings (rate limits, upload keys, webhook URLs).
- [ ] OPS-06 – Build `scripts/check_upload_queue.py` to print items currently processing plus their queue durations.
- [ ] OPS-07 – Document log rotation (journald or logrotate) so Pi disks don’t fill from FastAPI/gunicorn output.
- [ ] OPS-08 – Write a TLS/HTTPS quickstart showing how to reverse proxy FlipLens via Caddy/NGINX if exposed externally.
- [ ] OPS-09 – Update `scripts/pi/deploy_fliplens.sh` to optionally stash/un-stash local work before git pull.
- [ ] OPS-10 – Evaluate adding `Restart=on-failure` to the systemd unit and capture results + recommendation in docs.

---

## QA / Testing (AGENT_QA)

- [ ] QA-01 – Expand `tests/test_compliance.py` with cases for oversized images, NSFW heuristics, and mixed file formats.
- [ ] QA-02 – Add HEIC and DNG fixtures to `tests/fixtures/images/` to validate image conversion paths.
- [ ] QA-03 – Create `pi-app/tests/test_upload_rate_limit.py` covering missing auth headers and exceeding rate windows.
- [ ] QA-04 – Build snapshot tests for `/api/drafts` payloads (store golden JSON) to catch accidental schema changes.
- [ ] QA-05 – Write async concurrency tests for `/api/price` ensuring multiple requests respect the cache without race conditions.
- [ ] QA-06 – Use Starlette’s TestClient to request `/draft/{id}` HTML pages and assert key fields appear.
- [ ] QA-07 – Add lint/format checks (ruff or black) to CI or pre-commit for backend and mobile folders.
- [ ] QA-08 – Build contract tests ensuring `mobile/src/api.ts` parsing logic matches backend responses.
- [ ] QA-09 – Inject faults into ingest (mock compliance rejecting one photo) and assert clean-up occurs.
- [ ] QA-10 – Track coverage for `core/*` modules and document any gaps over 10% in a simple table.
- [ ] QA-11 – Add tests around new pagination/filtering on `/api/drafts` once implemented.
- [ ] QA-12 – Automate screenshot testing for the main mobile screens using Expo’s testing tools.

---

## 5. Parking lot (not for MVP)

- Discord bridge + `tools/agent_relay.py` multi-agent orchestration.
- Automated Vinted posting via bots/headless browsers.
- Vinted Pro API integration (business accounts).
- Non-clothing categories needing special handling (electronics, toys, etc.).
- CharityLoop client app / broader marketplace integrations.
