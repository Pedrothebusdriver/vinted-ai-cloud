# Backend draft flow

- Endpoint: `POST /process_image` (also available at `POST /api/drafts` for compatibility).
- Payload: `multipart/form-data` with at least one image as `file` (extras as `files`). Optional `metadata` JSON string supports `brand`, `size`, `colour`, `condition`, `description`, `status`, `title`, `price_mid`, `price_low`, `price_high`, `selected_price`.
- Behaviour: saves uploads to `data/uploads`, infers a title/brand/colour/price range from the filename, creates an in-memory draft entry, and returns the full draft JSON including its `id`, photos, and prices.
- Draft storage: kept in the `drafts` dict inside `app.py` with incremental IDs; thumbnails served from `/uploads/<filename>`.
- Related endpoints: `GET /api/drafts` (lists with filters/pagination), `GET /api/drafts/{id}` (detail), `PUT /api/drafts/{id}` (update title/description/status/price), and `/health` for connectivity checks.
- Mobile uses `POST /process_image` from the Upload screen; new drafts surface in the Drafts list via `GET /api/drafts`.

## Multi-photo payload + logging

- Send the primary image as `file` and any additional images as repeated `files` parts; order is preserved and the first photo is used as the cover.
- Response includes `photos` (array of `{id,url,filename}`), `photo_count`, `thumbnail_url`, and `cover_photo_url`.
- Log line to expect in the Flask console: `[FlipLens] /process_image received N files, created draft <id>`.

## Sanity check

- With the backend running locally (default `http://localhost:5055`): `python tools/dev_check_process_image_multi.py`
- Override the base URL if needed: `python tools/dev_check_process_image_multi.py http://<your-host>:5055`
