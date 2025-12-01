# Local connection notes (FlipLens)

- Mobile project root: /Users/petemcdade/vinted-ai-cloud/mobile
- Backend root: /Users/petemcdade/vinted_ai_cloud
- LAN IP: 192.168.0.21
- Backend port: 10000
- Base URL: http://192.168.0.21:10000
- Healthcheck: GET /health

## Connect screen behaviour

- Test Connection reads the current text box value or falls back to Config.apiBase.
- It normalizes the base URL, appends `/health`, and calls that URL.
- The success/error message always includes the exact tested URL.
- On success, it updates the global server state and saved servers with the normalized base URL.
- There are no hard-coded IP addresses or ports in the error messages.

## Upload flow

- Upload button calls `POST /process_image` with `multipart/form-data` (`file` for the first image, optional extra `files`, and optional `metadata` JSON string).
- Backend saves the image(s), infers attributes (title/brand/colour/price), and persists the draft in the in-memory `drafts` store.
- Response returns the created draft JSON including `id`, prices, photos, and thumbnail URL (served under `/uploads/<filename>`).
- Draft list and detail screens read from `GET /api/drafts` and `GET /api/drafts/{id}` using the same base URL.

## Tests

- Run Jest in the mobile project: `cd mobile && npm test -- --runInBand`
