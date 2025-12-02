# December War Plan (FlipLens)

Timeframe: now through end of December 2025. Objective: have FlipLens ready for a January soft launch where Pete can reliably push 10–20 items/day end-to-end.

## Pillars
1) Golden mobile path – one smooth path from photos → upload → draft edit → export, with no surprises.
2) Pi core stability – API, sampler, heartbeat, and metrics are boringly reliable.
3) Scraper + teaching loop – scrape UK listings, log teacher/student pairs, run evals, and feed corrections into heuristics.
4) Listing quality & speed – titles/descriptions/price in GBP feel right, with sharp photos and quick turnaround.
5) Operational sanity – simple, repeatable commands; minimal manual babysitting; clear status in README/docs.

## Week-by-week plan

### Week 1: Scraping and teaching the beast
- Finish the self-play/teacher-student loop: scrape UK listings, produce GBP-correct logs, and run evals that show field accuracy + price errors.
- Auto-learn consumes self-play + user corrections and updates heuristics config in GBP.
- Keep reports and logs reproducible; CLI commands work out of the box.

### Week 2: Golden mobile flow
- Make the mobile “golden path” rock solid: connect → select photos → upload → edit → export/paste.
- Harden Test Connection (timeouts, clear errors), reuse last known good backend on launch.
- Photo grouping predictable; upload status/errors readable; draft edit form stays visible with keyboard.

### Week 3: Reliability and image quality
- Pi services under systemd: API, sampler, heartbeat are always up; `/health` and `/metrics` stay green.
- Logs/evals rotate cleanly; thumbnail generation produces sharp 1x/2x images for cards.
- Review resize/compression so exported photos stay crisp for Vinted.

### Week 4: Internal soft launch rehearsal
- Run a full rehearsal: 10–20 items in a day through the loop, capture every manual step.
- Fix the blockers found in rehearsal; ensure exports (title/description/price/tags) are ready to paste.
- Keep README “Current status” and “Next focus” in sync with reality for handoff.

## Non-negotiables
- No new features that don’t support scraping, golden path, reliability, or listing quality.
- No major refactors unless they directly unblock those priorities.

## How to use this plan day to day
- 5-minute check-in each day: pick the pillar and week you’re advancing.
- Choose ONE big outcome per day; avoid splitting focus.
- Use agents for implementation; Pete handles testing/decisions and verifying the golden path.
- End-of-day brain dump: record what moved, what’s blocked, and what to try next.
