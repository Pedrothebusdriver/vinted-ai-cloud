# Actions for Pete (Shared Checklist)

Use this list so every agent is aligned on what we currently need from you.
Each item includes very simple “do this” steps.

---
## 1. Discord Bridge Bot Token
**Goal:** let the CLI read/reply to Discord when you’re AFK.

1. Visit https://discord.com/developers/applications → create a bot → copy its token.
2. On your Mac or Pi, run:
   ```bash
   mkdir -p ~/secrets && chmod 700 ~/secrets
   nano ~/secrets/discord_bot.json
   ```
3. Paste (replace placeholders):
   ```json
   {
     "token": "YOUR_BOT_TOKEN",
     "channel_ids": "ID_FOR_AI_TEST,ID_FOR_ALERTS"
   }
   ```
4. Save and tell us “bot token ready.” We’ll read it from that file and start the bridge.

---
## 2. Upload API Key Confirmation
**Goal:** secure `/api/upload` for Shortcut/Web uploads.

1. Decide the API key string you want (e.g., `UPLOAD_KEY=abc123`).
2. DM it to us or create a file `~/secrets/upload_key.txt` with just that value.
3. We will configure the Pi service to require `X-Upload-Key: <value>` and update the Shortcut/Web forms accordingly.

(If you already created a key, just confirm it’s `X-Upload-Key` so we can align docs + code.)

---
## 3. Vinted URL Seeds
**Goal:** manual testing with real listings while the new scraper finishes.

1. Open `docs/manuals/vinted-url-seeds.md` in the repo.
2. Under each category (Mens Hoodies, Womens Jeans, etc.), paste the Vinted item URLs you care about (one per line).
3. Commit/push if you’re editing locally, or just send the file back to us if that’s easier.
4. We’ll pull those URLs into the sampler immediately.

---
## 4. Shortcut/Web Upload Feedback
**Goal:** make sure you can upload from your phone right now.

1. Follow `docs/manuals/phone-upload.md` (Shortcuts) or `docs/manuals/web-upload.md` (once live).
2. Run a quick test (a couple of photos).
3. If anything breaks or is confusing, jot the draft number + symptom and ping us in Discord or edit this doc with notes.

---

Add more items here if you (or another agent) need new inputs from Pete. Keep the instructions simple so anyone can follow them.
