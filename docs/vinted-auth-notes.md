# Vinted Auth Notes (Nov 13)

## Credentials
- Stored on Pi at `~/secrets/vinted.json` (fields: `email`, `password`, `region`).

## Current Workdir
- All scratch logs/traces live under `~/vinted-ai-cloud/.tmp/vinted-auth/` on the Pi (not committed).
  - `session-trace-*.json`: raw request/response dumps (headers + bodies) from attempts to hit `/api/v2/catalog/items` via mobile UA.
  - `cf-challenge.html`: Cloudflare block page returned after session cookie is issued but before catalog fetch succeeds.
  - `notes.md`: quick timeline of the request sequence (login → token exchange → catalog fetch) and where the 403 shows up.

## Observations
1. Mobile app login (`/oauth/authorize` + `/oauth/token`) succeeds with the staged creds; we get an access token + refresh token.
2. Subsequent `GET https://www.vinted.co.uk/api/v2/catalog/items` calls (with auth headers + mobile UA) work for 1–2 requests, then Cloudflare responds with 403 + HTML challenge. The 403 happens regardless of whether we send the `Authorization: Bearer ...` header or rely on cookies.
3. Switching IPs (home vs. Pi) changes the timing slightly but the block still arrives once the `/catalog/items` endpoint is hit without the CF clearance token.

## Next Steps (either agent)
- Replay via the sampler with trace logging enabled:
  ```bash
  VINTED_TRACE_DIR=~/.tmp/vinted-auth python3 tools/vinted_sampler.py \
    --terms hoodie --per-term 2 --use-cloudscraper
  ```
  This now primes the session, routes requests through `cloudscraper`, and writes failing responses under `.tmp/vinted-auth/` automatically (`*api-fail*.json`, etc.).
- Investigate CF clearance requirements (maybe request `https://www.vinted.co.uk/` first, harvest `cf_clearance`, then hit `/api/v2/catalog/items`). The sampler already captures non-200 responses for later inspection.
- Alternative: use Playwright/Chromium with `--device="Pixel 7"` to fetch the catalog page, harvest `window.__NUXT__` JSON, and extract listings without touching the API.

Use these notes as a handoff starting point; feel free to move the logs if you prefer a different location.
