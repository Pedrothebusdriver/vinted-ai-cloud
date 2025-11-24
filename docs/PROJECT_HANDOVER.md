# FlipLens Project Handover (v1)

**Repo:** `Pedrothebusdriver/vinted-ai-cloud`  
**Local source of truth:** `/Users/petemcdade/vinted-ai-cloud`  
**Owner:** Pete  
**Last updated:** 2025-11-24

---

## 1) What FlipLens is

FlipLens is a Pi-hosted resale assistant + mobile companion app for Vinted sellers.  
Users take photos of items at home, FlipLens generates a draft listing (category, title, description, price, attributes), and produces a “Posting Pack” for easy manual posting into Vinted.  
Long-term, the same engine will support other resale marketplaces (eBay, Depop, etc.) via adapters.

---

## 2) This week’s single outcome (vertical slice)

By end of week, Pete can:

1. Open FlipLens on iPhone
2. Connect to Pi backend
3. Take/select photos
4. Tap **Create Draft**
5. See a draft with:
   - photos
   - category suggestion (any Vinted category)
   - price suggestion
   - title + description draft
   - editable attributes
6. Export a Posting Pack (copy-all + open Vinted helper)

Pretty UI and auto-posting are **not required** for this milestone.

---

## 3) Architecture snapshot

### Pi backend (FastAPI)
Path: `pi-app/`

Key endpoints:
- `GET /health` → `{status, version, schema_version?, uptime_seconds}`
- `POST /api/drafts` → create draft from uploaded photos + metadata
- `GET /api/drafts` → list drafts (filters/pagination)
- `GET /api/drafts/{id}` → draft detail
- `PATCH /api/drafts/{id}` → update/lock fields
- `POST /api/price` → price estimate for standalone metadata
- `GET /api/drafts/{id}/export` → posting payload

Core pipeline:
`pi-app/app/core/ingest.py`  
Stages: conversion → dedupe → compliance → OCR → metadata/attribute inference → pricing → draft persistence.

### Mobile app (Expo / React Native)
Path: `mobile/`

Core screens:
- ConnectScreen → set base URL + upload key
- UploadScreen → select photos, enter minimal metadata, call `POST /api/drafts`
- DraftListScreen → list/filters/refresh
- DraftDetailScreen → edit & view price/compliance/photos
- Export/Pack view → copy-all listing data + helper to open Vinted

---

## 4) Source-of-truth rule (critical)

**All coding agents must run locally on Pete’s Mac in the real repo**:

`/Users/petemcdade/vinted-ai-cloud`

Cloud/sandbox agents **cannot reliably push to GitHub** due to network/proxy limits.

Preflight before any agent work:
```bash
pwd
git remote -v
git status -sb
```
Must show:
- path ends with `vinted-ai-cloud`
- `origin` points to Pedrothebusdriver/vinted-ai-cloud
- status `## main...origin/main`

---

## 5) Agent lanes, responsibilities, and autonomy rules

### Lanes
- **AGENT_CORE** → backend only (`pi-app/`)
- **AGENT_MOBILE** → mobile only (`mobile/`)
- **AGENT_OPS** → scripts/systemd/docs ops only (`scripts/`, `systemd/`, ops docs)
- **AGENT_QA_AUTOMATION** → tests + safe helper tooling only (`tests/`, `tools/`)
- **AGENT_DESIGN (optional)** → mobile polish only (`mobile/`)

### Autonomy expectations
Each agent:
1. Pulls tasks from `docs/actions_for_pete.md`
2. Implements in batches (5–10 tasks)
3. Runs relevant tests
4. Commits + pushes to `origin/main`
5. Ticks tasks
6. Continues without asking permission unless truly blocked

Cross-lane changes are forbidden unless a task explicitly says so.

---

## 6) Orchestrator prompt (daily swarm driver)

Create a Codex task named **AGENT_ORCHESTRATOR**, running locally, with:

```text
You are AGENT_ORCHESTRATOR running LOCALLY in /Users/petemcdade/vinted-ai-cloud.

Preflight: pwd must be /Users/petemcdade/vinted-ai-cloud and origin remote must exist. If not, STOP.

Then:
- Read docs/actions_for_pete.md.
- Take next 10 unchecked tasks per lane (CORE/MOBILE/OPS/QA).
- Dispatch to lane agents with "no permission needed, keep going".
- Lane agents must implement -> test -> commit -> push -> tick tasks.
- When a lane finishes, immediately pull the next 10 for that lane.
- Keep lanes busy until 40 tasks are completed or a real blocker appears.

Return a single summary with tasks completed + commit SHAs.
```

---

## 7) “Apple-style AI” bootstrap plan

We use a pretrained on-device/fast vision model as a first-pass guesser:
- coarse category suggest
- colour/material/shape hints
- confidence scores

Then we improve accuracy by collecting real Vinted-specific corrections and fine-tuning resale-focused models.  
This gives a “wow” moment now and a defensible moat later.

---

## 8) Current repo state (truth)

Local/GitHub `main` should match:
- `git status -sb` → `## main...origin/main`
- `git log --oneline -5` shows latest swarm commits

If agent summaries don’t appear in GitHub history, assume they were done in the wrong environment and re-apply in source-of-truth repo.

---

## 9) Next checkpoints for a new chat

When starting a fresh ChatGPT thread, paste a condensed handover like:

```text
Project: FlipLens (vinted-ai-cloud).
Goal: vertical slice this week (connect → upload → draft → export).
Source-of-truth repo: ~/vinted-ai-cloud.
Agents must run locally; lanes CORE/MOBILE/OPS/QA.
Use AGENT_ORCHESTRATOR daily.
```

---

## 10) Useful commands

Pull latest:
```bash
cd ~/vinted-ai-cloud && git pull origin main
```

Start Expo:
```bash
cd ~/vinted-ai-cloud/mobile && npx expo start --localhost -c
```

Check Pi health:
```bash
curl http://192.168.0.16:8081/health
```

---

**End of handover.**
