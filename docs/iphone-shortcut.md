# iPhone Shortcut — Upload to Vinted Pi

This Shortcut lets you pick photos on your phone and upload them straight to the
Pi’s `/api/upload` endpoint so the draft appears in Discord within a minute.

## Prerequisites
- Public base URL: `http://100.85.116.21:8080`
- Endpoint: `POST /api/upload` (multipart form)
- Upload API key (ask in Discord; required whenever the endpoint is exposed publicly)
- Fields:
  - `files` — one entry per image (binary data)
  - optional `metadata` — JSON string with hints (brand, size, etc.)

## Shortcut Steps
1. Open the **Shortcuts** app → tap **+** to create a new shortcut (e.g., “Send
to Vinted Pi”).
2. Add the following actions in order:

   1. **Select Photos**
      - Allow Multiple: On (or Off if you only want single uploads)
   2. **Repeat with Each** (automatically wraps the next actions)
   3. **Get Contents of** `Repeat Item` → **Convert to JPEG** (optional but keeps
      everything JPG)
   4. **Encode Media** → set “Encode To” = “Base64” (optional; see note)
   5. **Text** (JSON metadata, optional). Example:
      ```json
      {
        "source": "iphone-shortcut",
        "note": "Bedroom hoodie drop"
      }
      ```
   6. **Get Contents of URL**
      - Method: **POST**
      - URL: `http://100.85.116.21:8080/api/upload`
      - Request Body: **Form**
        - Field 1: `files` → tap **File**, choose **Repeat Item** (if you didn’t
          Base64-encode) or choose **Encoded Media** → set MIME type `image/jpeg`.
        - Field 2 (optional): `metadata` → Text from step 5.
      - Headers:
        - `Accept: application/json`
        - `X-Upload-Key: YOUR_KEY_HERE`
   7. **Get Dictionary from Input** → parses the JSON response.
   8. **Show Notification** → Text: `Uploaded draft #${Dictionary[
        "item_id"]}!`

## Notes
- Step 4 (Base64) is optional. If you skip it, ensure the **Get Contents of
  URL** form field is set to “File” and points directly to `Repeat Item`.
- You can duplicate the shortcut and hard-code metadata (e.g., category =
  "hoodie"), or prompt for text each run.
- The API responds with `{"queued": true, "item_id": N}`; drafts appear at
  `http://100.85.116.21:8080/draft/N` and in the Discord draft channel.
- If you don’t include the `X-Upload-Key` header (or use the wrong key), the
  Shortcut will show a 401 error and the uploads will be rejected.

## Testing
1. Run the shortcut with a couple of product photos.
2. Watch the draft channel (`#vinted-bot`) for the message.
3. Tap the link to review/edit the draft from Safari on your phone.
4. If something looks wrong, copy the draft URL back here so we can improve the
   pipeline.

Feel free to tweak the shortcut (e.g., add a menu of metadata presets) and send
any improvements back so we can include them for other testers.
