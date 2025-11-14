# Vinted Auth Notes (Nov 13)

The sampler can now log in with Vinted’s mobile OAuth flow, cache the access/
refresh tokens, and fetch `/api/v2/catalog/items` without tripping Cloudflare.
This page explains how to configure the credentials and run the new workflow.

## 1. Credentials file
Create `~/secrets/vinted.json` (never commit it). Example template lives at
`docs/examples/vinted.json.example`. Required fields:

```json
{
  "email": "tester@example.com",
  "password": "super-secret",
  "client_id": "MOBILE_APP_CLIENT_ID",
  "client_secret": "MOBILE_APP_CLIENT_SECRET",
  "scope": "item_api offline_access",
  "region": "https://www.vinted.co.uk"
}
```

- `client_id` / `client_secret` come from the mobile app (sniff via mitmproxy or
  the official docs).
- `region` can be a full base URL (`https://www.vinted.de`) or just a domain
  suffix (`co.uk`, `fr`, etc.). Leave it blank to keep the CLI `--base` value.

## 2. Token + trace storage
- OAuth cache: `.tmp/vinted-auth/token.json` (override with
  `VINTED_SESSION_CACHE`).
- Trace dumps: `.tmp/vinted-auth/*` (override with `VINTED_TRACE_DIR`). Every
  non-200 response writes `*-<timestamp>.json` so you can inspect headers/body
  when Cloudflare blocks a request.

## 3. Running the sampler manually
```bash
source pi-app/.venv/bin/activate
export VINTED_CREDENTIALS_PATH=~/secrets/vinted.json
export VINTED_SAMPLER_TERMS="hoodie,jeans,jacket"
export VINTED_SAMPLER_PER_TERM=4
python tools/vinted_sampler.py \
  --catalog-ids "1907,1908,1192" \
  --use-cloudscraper \
  --upload-key "$UPLOAD_KEY_IF_NEEDED"
```

Key flags/envs:
- `--catalog-ids` – restricts results to specific catalog IDs (handy to keep it
  clothing-only).
- `--upload` / `--upload-key` – if you want the sampler to push straight into
  `/api/upload`, supply the API key we now require.
- `--trace-dir` – point at a writable folder if you want traces elsewhere.

## 4. Nightly automation
`SAMPLER_SOURCE=vinted` now flips `scripts/run_sampler_cycle.sh` into this
authenticated mode. The script automatically maps `SAMPLER_BUCKETS` to the
sampler’s `--terms`, so setting:

```bash
SAMPLER_SOURCE=vinted
SAMPLER_BUCKETS=hoodies,jeans,trainers
SAMPLER_PER_BUCKET=12
```

will run `tools/vinted_sampler.py` with matching knobs before the eval cycle.
`sampler.log` records which source ran each loop.

## 5. Troubleshooting checklist
1. **401s in log** – check `~/secrets/vinted.json` is readable by the `pi`
   user and the `client_id/client_secret` are valid. Deleting the token cache
   forces a fresh login.
2. **403s / HTML errors** – look at `.tmp/vinted-auth/api-fail-*.json` to see
   the Cloudflare challenge. Running with `--use-cloudscraper` and `prime_session`
   usually clears it; otherwise rotate IPs or pause for a few minutes.
3. **Empty folders** – ensure `SAMPLER_BUCKETS` (or `--terms`) contain actual
   clothing keywords; Vinted will happily return zero matches for nonsense.
4. **Upload failures** – `/api/upload` now requires an API key. Set
   `VINTED_UPLOAD_KEY` or pass `--upload-key` explicitly.

Ping `@codex` in Discord if you hit a blocker; include the relevant trace file
from `.tmp/vinted-auth/` so we can reproduce it quickly.
