# STATUS – FlipLens / Vinted AI Core

This file is maintained mainly by the **Status / Pete Helper Agent**.

Its purpose is to give Pete a quick, human-readable view of:
- What has changed recently.
- What is ready for him to test.
- What decisions or inputs are needed from him.

---

## Summary (last updated: 2025-11-17)

- FlipLens PRD + `docs/actions_for_pete.md` now define a single, trimmed backlog focused on the Pi core + Expo client, so every agent lands on the same MVP plan immediately.
- Ops shipped `scripts/sqlite_migrate.py` and `docs/manuals/sqlite_migration.md` so the Pi database can be upgraded (drafts/photos schema) with a single command + documented backup steps.
- Agent playbooks were refreshed: `docs/manuals/agent-naming.md` covers the Playwright Agent1 service layout, and Expo/phone upload manuals document how to run the current mobile flows.
- Discord relay + compliance tooling landed earlier in the week (agent relay scripts, bridge systemd units, expanded `tests/test_compliance.py`), giving us a stable comms + QA foundation while we refactor the core.

---

## Ready for Pete to test

1. **Core health endpoint**
   - Command: `curl http://100.85.116.21:8080/health`
   - Success: JSON payload like `{"status":"ok","version":"<git_sha>","uptime_seconds":...}` and HTTP 200.

2. **Compliance regression tests**
   - Command: `python -m pytest tests/test_compliance.py`
   - Success: all tests green (`3 passed`), showing Laplacian blur + face/HOG checks behave on your machine/Pi before we touch ingest again.

3. **Expo upload flow (current mobile scaffold)**
   - Commands:
     ```bash
     cd ~/vinted-ai-cloud/mobile
     npx expo start --web  # or --tunnel for phone testing
     ```
   - Steps: Connect to the Pi via the Connect screen (`/health`), run an upload (camera or gallery) to `/api/upload`, and confirm a new draft appears in the Pi UI.
   - Success: Upload succeeds, draft shows brand/price fields populated, and Expo shows the success banner described in `docs/manuals/expo-upload.md`.

---

## In progress (by agents)

_A short list of major areas agents are actively working on (e.g. core ingest, /api/drafts endpoint, mobile Drafts screen)._

---

## Decisions / questions for Pete

_The Status agent should put any open decisions or questions here for Pete to review in the chat (e.g. “Choose between A/B for category UI”, “Approve moving core to mini PC”)._
