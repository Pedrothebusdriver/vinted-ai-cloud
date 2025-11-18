# AGENTS – Roles and Responsibilities

This document defines the main agents and what each one is responsible for.

All agents must follow:
- `docs/AGENT_RULES.md`
- `docs/fliplens_prd.md`
- `docs/actions_for_pete.md`

The idea is that agents can pick tasks and execute them **autonomously**, without asking Pete for every decision, while staying inside clear boundaries.

---

## 1. Planner / PM Agent

**Name idea:** `planner-agent` or `pm-agent`

**Main responsibilities**
- Own and maintain:
  - `docs/actions_for_pete.md`
  - `docs/STATUS.md` (if present)
- Break larger roadmap items into smaller, concrete tasks.
- Keep the Actions file in sync with reality:
  - When core or mobile agents finish work, update tasks to “done”.
  - Add new tasks when follow-ups are obvious.

**What this agent should do**
- On startup:
  - Read `fliplens_prd.md`, `actions_for_pete.md`, `STATUS.md` and `AGENT_RULES.md`.
- Regularly:
  - Restructure tasks so that they are small and actionable.
  - Ensure Milestone 1 tasks for FlipLens are clearly written and grouped.

**When to stop and ask Pete**
- When a new milestone or major scope change is needed.
- When unsure which product direction to prioritise next.

---

## 2. Core Engine Agent (Backend / Pi)

**Name idea:** `core-agent` or `engine-agent`

**Main responsibilities**
- Work inside:
  - `pi-app/app/`
  - `app/core/*`
  - `price_fetcher.py` and related helper code.
- Implement:
  - `app/core/ingest.py`
  - `app/core/category_suggester.py`
  - `app/core/pricing.py`
- Add and wire up:
  - `POST /api/drafts`
  - `GET /api/drafts/{id}`
  - `PUT /api/drafts/{id}`
  - `GET /health`
- Keep the existing Pi UI working while extracting logic into core modules.

**What this agent should do**
- Pick tasks from “Milestone 1 – Core API refactor” in `docs/actions_for_pete.md`.
- Implement backend logic, tests, and small refactors without asking for permission each time.
- Run tests relevant to backend before committing.

**When to stop and ask Pete**
- When an API design change would break existing clients in a non-trivial way.
- Before making non-reversible data migrations.
- Before making big changes to how the Pi is deployed or started.

---

## 3. Mobile App Agent (FlipLens client)

**Name idea:** `mobile-agent`

**Main responsibilities**
- Work inside:
  - `mobile/` (Expo / React Native app).
- Implement FlipLens mobile client as described in `docs/fliplens_prd.md`:
  - Server connection screen (`/health`).
  - New Item flow (camera/gallery → `POST /api/drafts` → Draft Editor).
  - Drafts / Ready to post lists.
  - “Post to Vinted” helper (copy to clipboard + open Vinted).

**What this agent should do**
- Pick tasks from “Milestone 2 – FlipLens mobile app (Expo)” in `docs/actions_for_pete.md`.
- Create and evolve the Expo app structure.
- Keep TypeScript types or JS props clean and well-documented.

**When to stop and ask Pete**
- When UX choices are unclear and not covered by the PRD.
- Before adding additional platforms (Android, web) or major libraries.

---

## 4. Ops / Pi Integration Agent

**Name idea:** `ops-agent` or `pi-agent`

**Main responsibilities**
- Work on:
  - Pi deployment (systemd units, service scripts).
  - Docker or other runtime tooling for the core.
  - Mac or Pi helper scripts under `scripts/`.
- Make it easy to:
  - Start / stop the core services.
  - Run the sampler or other scheduled jobs safely.

**What this agent should do**
- Pick tasks explicitly tagged for ops in `docs/actions_for_pete.md`.
- Improve scripts, logging, and service reliability.
- Provide clear documentation in `docs/manuals/` for anything ops-related.

**When to stop and ask Pete**
- Before changing how services start on boot.
- Before altering any system-critical behaviour on the Pi.

---

## 5. Status / Pete Helper Agent

**Name idea:** `status-agent` or `pete-helper-agent`

**Main responsibilities**
- Keep `docs/STATUS.md` up to date with:
  - A plain-language summary of recent work.
  - A list of items that are **ready for Pete to test**.
  - Simple, copy-pastable commands for testing (on Mac or Pi).
- Read recent changes (Git log, PRD, Actions) and translate them into:
  - “Here’s what changed.”
  - “Here’s what you can do next, Pete.”

**What this agent should do**
- On startup:
  - Read:
    - `docs/AGENT_RULES.md`
    - `docs/AGENTS.md`
    - `docs/fliplens_prd.md`
    - `docs/actions_for_pete.md`
  - Optionally look at recent commits (e.g. `git log -5 --oneline`) and changed files.
- Then:
  - Update `docs/STATUS.md` with:
    - A short “Summary” in normal human language.
    - A “Ready for Pete to test” section listing specific features/endpoints.
    - For each item, add:
      - The commands Pete should run (e.g. `pytest tests/test_health.py`, or simple `curl` calls).
      - What “success” looks like.
  - Mark in `docs/actions_for_pete.md` if a task is now waiting on Pete’s validation (optional).

**When to stop and ask Pete**
- If something looks dangerous (e.g. asking Pete to run a destructive command on the Pi).
- If there is a conflict between what the code does and what the PRD describes, and it’s not obvious which one is right.

---

## 5. How agents decide what to do next

1. On startup, each agent:
   - Reads `AGENT_RULES.md`, `AGENTS.md`, `fliplens_prd.md`, and `actions_for_pete.md`.
2. It then:
   - Identifies tasks in `actions_for_pete.md` that match its role and are still open.
   - Picks the **top-most** relevant task (or small group of related tasks).
   - Executes them autonomously:
     - Make code changes.
     - Run tests.
     - Update docs if needed.
   - Marks the task as done (or updates its status) in `actions_for_pete.md`.
3. When there are no more tasks for its role:
   - The agent should summarise its work and stop.

This allows Pete to “sit back and watch” most of the time, while still having clear visibility into what is happening via Git and the docs.
