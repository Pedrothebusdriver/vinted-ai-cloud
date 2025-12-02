# Bulk upload mode (mobile)

- Entry point: Upload screen toggle “Bulk upload multiple items”.
- Flow: pick many photos (up to MAX_BULK_PHOTOS). Photos are sorted by `creationTime` and grouped; a new draft starts when the gap between photos exceeds `BULK_TIME_GAP_SECONDS` (default 20s). Oversized groups are split into chunks of `MAX_PHOTOS_PER_DRAFT` (default 8).
- Upload behaviour: each group is sent sequentially to the existing `POST /process_image` endpoint with the same multipart fields (`file` + repeated `files`). No backend changes.
- Progress: shows “Creating drafts X / Y”; on completion navigates to Drafts and reports successes/failures.
- Config knobs (mobile/src/config.ts):
  - `BULK_TIME_GAP_SECONDS = 20`
  - `MAX_PHOTOS_PER_DRAFT = 8`
  - `MAX_BULK_PHOTOS = 80`
  - `INTER_REQUEST_DELAY_MS = 250`
- Caveats: grouping relies on capture timestamps; if photos lack metadata or are out of order, grouping may not perfectly match actual items. Oversized groups are split in-order.
