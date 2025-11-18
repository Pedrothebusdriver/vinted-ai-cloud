# Actions for Pete – FlipLens MVP

This file tracks what needs to happen **next** for the FlipLens MVP.  
The goal is to keep this simple and focused so we don’t get distracted.

---

## 0. Ground rules

- FlipLens v1 = **assistant for home Vinted sellers** (not Pro yet).
- Engine runs on the **Raspberry Pi** for now.
- No direct bot posting to Vinted in MVP. We generate drafts and then help the user post manually in the Vinted app.
- Multi-agent / Discord relay stuff is **paused** until FlipLens MVP is working.

---

## 1. Setup & housekeeping

### 1.1 PRD in repo

- [ ] Ensure `docs/fliplens_prd.md` exists with the current FlipLens MVP PRD.

### 1.2 Clean mental space

- [ ] Treat this file as the single source of truth for “what to do next”.
- [ ] Don’t add long brain dumps here – just clear, small tasks.

---

## 2. Milestone 1 – Core API refactor (Vinted AI Core)

Goal: Turn the existing FastAPI Pi app into a reusable “Vinted AI Core” with clean HTTP endpoints.

### 2.1 New core modules

- [ ] Create `app/core/ingest.py`
  - Function to accept uploaded images and:
    - Convert / normalise images.
    - Call OCR to get text.
    - Extract brand and size from OCR text (reuse existing logic).
    - Estimate dominant colour.
    - Call category suggester.
    - Call pricing helper.
    - Build and return a draft object.

- [ ] Create `app/core/category_suggester.py`
  - Load `data/vinted_categories.json` (Vinted category tree).
  - Implement `suggest_categories(hint_text, ocr_text, filename)`:
    - Use keyword + fuzzy matching to return a ranked list of category candidates.

- [ ] Create `app/core/pricing.py`
  - Wrap existing pricing helper logic.
  - Implement `suggest_price(brand, category_id, size, condition)`:
    - Returns `{low, mid, high}`.
    - Use simple in-memory cache keyed by `(brand, category_id, size)`.

### 2.2 API endpoints

- [ ] Add `GET /health`
  - Returns `{ "status": "ok", "version": "<git_sha_or_semver>" }`.

- [ ] Add `POST /api/drafts`
  - Accepts images + optional hint text.
  - Uses core modules to produce a draft.
  - Stores the draft in SQLite.
  - Returns the draft payload.

- [ ] Add `GET /api/drafts/{id}`
  - Returns stored draft and metadata.

- [ ] Add `PUT /api/drafts/{id}`
  - Allows updates from the mobile app (title, description, category, price, status).

- [ ] Expose or tidy `POST /api/price`
  - Make sure pricing logic is in `core/pricing.py` and used by `/api/drafts`.

### 2.3 Database tweaks

- [ ] Ensure SQLite schema has a `drafts` table with at least:
  - `id`
  - `created_at`
  - `updated_at`
  - `status` (draft, ready, posted)
  - `brand`
  - `size`
  - `colour`
  - `category_id`
  - `condition`
  - `title`
  - `description`
  - `price_low`
  - `price_mid`
  - `price_high`
  - `selected_price`

- [ ] Ensure `photos` table is linked to drafts and stores:
  - `id`
  - `draft_id`
  - `file_path`
  - `position` (ordering).

- [ ] Add a very simple migration note (even if it’s just SQL in another doc).

### 2.4 Keep Pi UI working

- [ ] Update existing Pi HTML routes to use the new core functions.
- [ ] Confirm basic flows on the Pi still work:
  - Upload item.
  - See draft in the Pi UI.
  - Price suggestions still appear.

---

## 3. Milestone 2 – FlipLens mobile app (Expo)

*(We do this after Milestone 1 starts, but it’s listed here so we see the big picture.)*

- [ ] Create `mobile/` folder with an Expo app.
- [ ] Implement “Connect to server” screen (`/health`).
- [ ] Implement “New Item” flow (camera/gallery → `POST /api/drafts` → Draft Editor).
- [ ] Implement Drafts / Ready to post lists.
- [ ] Implement “Post to Vinted” helper (copy to clipboard + open Vinted app + instructions).

---

## 4. Parking lot (not for MVP)

These are ideas deliberately **not** being worked on right now:

- Discord bridge + `tools/agent_relay.py` multi-agent orchestration.
- Automated Vinted posting via bots or headless browser.
- Vinted Pro API integration (for business accounts).
- Non-clothing categories that need special handling (electronics testing, toys with safety issues, etc.).
- CharityLoop client app.

We’ll pull from this list only after the FlipLens MVP is running on the Pi.

---
