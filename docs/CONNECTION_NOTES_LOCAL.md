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

## Tests

- Run Jest in the mobile project: `cd mobile && npm test -- --runInBand`
