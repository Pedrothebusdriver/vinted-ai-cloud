# BACKEND DRAFTS NOTES

## Mobile expectations
- Base URL comes from `Config.apiBase` (defaults to `http://192.168.0.21:10000`); trailing slash is stripped.
- `POST /api/drafts` is called from the Upload screen with `FormData`:
  - Fields: `files` (one or many images), optional `metadata` JSON string (brand, size, condition, title, etc.).
  - Response is parsed as a draft detail and the app looks for `id`/`draft_id`/`item_id`/`draft.id`.
- `GET /api/drafts?status=<draft|ready>&limit=<n>&offset=<n>` lists drafts; response must be an array. Items use keys: `id`, `title`, `status`, `brand`, `size`, `colour`, `updated_at`, `price_mid`, `thumbnail_url`, `photo_count`.
- `GET /api/drafts/{id}` returns a single draft detail with the summary fields plus `description`, `condition`, `price_low`, `price_high`, `selected_price`, and `photos` (array of `{id,url}`/`optimised_path`/`original_path`).
- `PUT /api/drafts/{id}` sends JSON `{title?,description?,price?,status?}`; body is ignored, only HTTP 2xx matters.
- All draft routes may include `X-Upload-Key` header; it is not validated yet.
- Error handling: mobile surfaces `detail`/`error` from JSON bodies when status is not OK.

## Implemented backend (app.py)
- Added temporary in-memory store: `drafts: Dict[int, Dict[str, Any]]` and `next_draft_id`.
- Routes (all under `/api/drafts`):
  - `GET /api/drafts`: optional filters `status`, `brand`, `size`, pagination `limit` (default 20, max 100) and `offset`. Returns list of summaries (includes `photo_count` and `thumbnail_url`).
  - `GET /api/drafts/<id>`: returns draft detail or `{ "detail": "Not found" }` with 404.
  - `POST /api/drafts`: accepts JSON or `FormData` with `files` + optional `metadata` JSON string. Assigns an ID, stamps `updated_at`, stores brand/size/colour/condition/description/price fields when provided, and returns the created draft detail (201). Photos are acknowledged and mirrored back as placeholder URLs.
  - `PUT /api/drafts/<id>`: updates title/description/status/price (price is stored as `selected_price` and used as `price_mid` if missing) and returns updated detail.
- Added a global 404 handler that returns `{ "detail": "Not found" }` to keep mobile-friendly errors. `/health` remains unchanged.

## Sample interactions
- List: `curl -s http://192.168.0.21:10000/api/drafts`
- Create (JSON): `curl -s -X POST http://192.168.0.21:10000/api/drafts -H "Content-Type: application/json" -d '{"title":"Test draft","brand":"Test","price_mid":55}'`
- Create (FormData with metadata string): `curl -s -X POST http://192.168.0.21:10000/api/drafts -F 'files=@/path/photo.jpg' -F 'metadata={\"brand\":\"Nike\",\"size\":\"M\"}'`
- Detail: `curl -s http://192.168.0.21:10000/api/drafts/1`
