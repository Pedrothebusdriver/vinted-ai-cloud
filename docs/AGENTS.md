# Agents – Roles & Responsibilities

This repo is for the FlipLens MVP. All agents must:
- Read `docs/fliplens_prd.md` (product vision).
- Read `docs/actions_for_pete.md` (current tasks).
- Read this file and `docs/AGENT_RULES.md` before they start work.

## AGENT_CORE – Backend / Vinted AI Core

**Scope**
- All backend logic that powers FlipLens.
- Mainly under:
  - `pi-app/app/`
  - `pi-app/app/core/`
  - Backend-related tests.

**Main responsibilities**
- Implement `build_draft_from_images` in `core/ingest.py`.
- Implement `suggest_categories` in `core/category_suggester.py`.
- Implement `suggest_price` in `core/pricing.py`.
- Add and maintain API endpoints for:
  - `GET /health`
  - `POST /api/drafts`
  - `GET /api/drafts/{id}`
  - `PUT /api/drafts/{id}`
  - `POST /api/price`
- Keep the Pi HTML UI working while gradually moving logic from `main.py` into `core/*`.

## AGENT_MOBILE – FlipLens app (Expo)

**Scope**
- The FlipLens mobile client in `mobile/`.

**Main responsibilities**
- Scaffold the Expo app.
- Implement:
  - Server connection screen using `/health`.
  - “New Item” flow: camera/gallery → `POST /api/drafts` → Draft editor.
  - Drafts + “Ready to post” lists.
  - “Post to Vinted” helper (clipboard + open Vinted app + on-screen checklist).

## AGENT_OPS – Infra / Pi

**Scope**
- Scripts and configs to run Vinted AI Core reliably, mainly:
  - `scripts/`
  - `pi-app/` deployment/startup configuration.

**Main responsibilities**
- Make it easy to start/restart the FastAPI app on the Pi.
- Add/maintain systemd service files for the backend where needed.
- Avoid touching Pete’s personal macOS login items unless explicitly asked.

## AGENT_QA – Tests & Refactors

**Scope**
- Tests in `tests/` and any new test folders.

**Main responsibilities**
- Add tests for new backend/mobile behaviour introduced by other agents.
- Improve existing tests (e.g. compliance, events).
- Make small, safe refactors to reduce bugs and improve clarity.

## Future Agents (parked for now)

These roles are *not* active until `docs/actions_for_pete.md` says otherwise:
- AGENT_DISCORD – Discord bridge / multi-agent orchestration.
- AGENT_CHARITYLOOP – Charity shop intake app.
- AGENT_VINTED_PRO – Official Vinted Pro API integration.

If you are running as one of these future agents, do nothing until explicitly enabled.
