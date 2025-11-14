# Project Scope — Vinted Draft Assistant

## Mission
Create a cross-platform assistant that lets anyone selling on Vinted (and, later,
other marketplaces like eBay/Depop) capture item photos and instantly receive a
ready-to-post draft (title, attributes, pricing hints, compliance checks). The
result should remove the manual friction of listing clothes online.

## Product Pillars
1. **Capture Anywhere** — mobile-first UX (iOS/Android/web) to select or shoot
   images, optionally add context (brand/size/price target), and submit in seconds.
2. **Instant Drafts** — backend analyses photos (vision + OCR + heuristics) to
   infer brand, size, colour, item type, condition, and generate a Vinted-ready
   title + recommended tags/price. Drafts should be shareable + editable.
3. **Compliance & Safety** — automatic checks for prohibited content (faces,
   logos, restricted items) before drafts reach marketplaces.
4. **Marketplace Integrations** — start with Vinted draft export; future phases
   push directly to eBay/Depop/etc. using their APIs.
5. **Learning Loop** — every correction feeds back into the model/heuristics to
   improve accuracy over time.

## Phase Plan
| Phase | Outcomes | Notes |
| --- | --- | --- |
| 0. Foundations (current) | Stabilise Pi pipeline (auth sampler, manual uploads, Discord visibility) | Required before exposing to users |
| 1. Manual Alpha | Give selected users (incl. you) an easy mobile upload path (Shortcut/web form) that returns Discord draft links in <1 min | Validate accuracy + UX feedback |
| 2. Mobile App MVP | Native app (start with iOS) with login, item capture, draft history, push notifications | Backend evolves into multi-tenant API |
| 3. Marketplace Push | Add eBay/etc listing export, price guidance, inventory tracking | Requires OAuth + compliance for each platform |
| 4. Scale & Monetise | Subscriptions or pay-per-draft, analytics dashboard, team workflows | Guardrails + support tooling |

## Near-Term Deliverables (shared backlog)
1. **Authenticated sampler** (Codex CLI) — finish Vinted Playwright/mobile flow so overnight runs use real clothing photos.
2. **Manual upload funnel** — expose `/api/upload` publicly (with rate limits) + document iOS Shortcut so you can test from your phone today.
3. **Discord observability** — ensure drafts, alerts, eval snapshots stay separated (ai-test, general, heartbeat, alerts).
4. **Deep dive & security** — hardware roadmap, service hardening, secret hygiene.
5. **App scope session** — align on MVP screens, data contracts, and timelines once (1)-(3) are stable.

## Open Questions for Scope Session
- User auth/identity: email? social login? tie to marketplace credentials?
- Pricing model: free tier vs. subscription vs. per-draft credits?
- Storage/retention: how long to keep user photos + labels? GDPR considerations?
- Marketplace priority order after Vinted (eBay, Depop, Poshmark, …)?
- Hosting plan for production backend (Render vs. dedicated mini PC vs. cloud VM)?

Use this document as the shared blueprint; iterate here as we refine features
with the team.
