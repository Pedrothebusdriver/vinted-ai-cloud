# Vinted Auth Notes (updated)

The sampler can pull real Vinted listings when given a small JSON config. It
reuses an existing authenticated session (bearer token or cookie) rather than
performing the OAuth login flow itself.

## 1. Credentials file
Create `~/secrets/vinted.json` (never commit it). Supported fields:

```json
{
  "region": "https://www.vinted.co.uk",
  "access_token": "BEARER_OR_JWT_TOKEN",
  "cookie": "SECURE_LOGGED_IN_COOKIE_HEADER",
  "headers": {
    "User-Agent": "Mozilla/5.0 ...",
    "Accept-Language": "en-GB,en;q=0.9"
  }
}
```

- `region` can be a full base URL (`https://www.vinted.de`) or just the suffix
  (`co.uk`, `fr`, etc.). Defaults to `https://www.vinted.co.uk`.
- `access_token` is preferred (sniff from the mobile app/API via
  mitmproxy/Proxyman).
- `cookie` can be used instead (grab the raw `Cookie` header from a logged-in
  browser session).
- `headers` is optional for extra headers to merge into each request.

Set `VINTED_CREDENTIALS_PATH` to override the location if needed; otherwise the
sampler reads `~/secrets/vinted.json`.

## 2. Running the sampler manually
```bash
source .venv/bin/activate
export VINTED_CREDENTIALS_PATH=~/secrets/vinted.json
export SAMPLER_SOURCE=vinted
export SAMPLER_BUCKETS="hoodies,jeans,jackets"
python tools/sampler.py
```

## 3. Nightly automation
On the Pi, `scripts/run_sampler_cycle.sh` will:

- Default to `SAMPLER_SOURCE=vinted` when `~/secrets/vinted.json` exists,
  otherwise fall back to `openverse`.
- Use `SAMPLER_BUCKETS` / `SAMPLER_PER_BUCKET` / `SAMPLER_TOTAL_LIMIT` from
  `pi-app/.env` (or env overrides).
- Post-process evals via `tools/eval_report.py` and notify
  `/api/learning/notify` on port `10000`.

## 4. Troubleshooting checklist
1. **401s/403s** – refresh the bearer token or cookie in
   `~/secrets/vinted.json`; expired sessions are the most common failure.
2. **Empty buckets** – make sure `SAMPLER_BUCKETS` contains real clothing
   queries; the sampler caps per-bucket fetches to keep request volume low.
3. **Repeated rejections** – compliance checks (size/blur/face/body) run on
   each downloaded image; inspect `data/online-samples/<date>/_summary.json`
   to see which files were dropped and why.
