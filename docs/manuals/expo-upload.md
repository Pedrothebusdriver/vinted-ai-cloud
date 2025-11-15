# Expo Mobile Upload Prototype

Use this guide when you want the richer camera/library experience instead of
the basic iOS Shortcuts flow. The Expo app talks to the same Pi uploader
(`http://100.85.116.21:8080/api/upload`) and shows draft IDs inline so you know
each run succeeded.

## 1. Prerequisites
- Node.js 18+ with `npm` or `yarn`.
- Expo CLI (`npx expo` ships with npm 7+).
- Access to the Pi uploader (`http://100.85.116.21:8080` on your network or via
  tunnel).
- API key for `/api/upload` (same as Shortcuts/web).

Optional: Expo Go on your phone (free in iOS/Android stores) if you want to
test on-device.

## 2. Configure the app
```bash
cd ~/vinted-ai-cloud/mobile
cp .env.local.example .env.local        # only if it doesn’t exist
```

Edit `.env.local` (or set env vars before launching):
```
EXPO_PUBLIC_API_BASE=http://100.85.116.21:8080
EXPO_PUBLIC_UPLOAD_KEY=<your X-Upload-Key>
```

## 3. Install dependencies (first run)
```bash
npm install
```

## 4. Launch Expo
- **Web (quickest):**
  ```bash
  npx expo start --web
  ```
- **Tunnel / Expo Go:**
  ```bash
  npx expo start --tunnel
  ```
  Scan the QR code with Expo Go (iOS/Android).
- **iOS simulator (Mac only):**
  ```bash
  npx expo start --ios
  ```

When the bundler finishes you’ll see the upload UI with:
- **Select Photos** button (multi-select existing images)
- **Take Photo** button (camera capture)
- Optional metadata text box
- Status/draft output area

## 5. Smoke-test both flows
1. Tap **Select Photos** → choose at least two images → tap **Upload**.
   - Watch the status line; it prints each uploaded filename followed by
     `Draft #<id>` when `/api/upload` accepts the batch.
   - In Discord (`#vinted-ai-group-chat`) you should see the draft post within
     ~1 minute.
2. Tap **Take Photo** → capture a new picture → **Use Photo** → **Upload**.
   - Confirm another draft number appears and shows up in Discord.

If either step fails, note the on-screen error and check the Pi logs
(`journalctl --user -u discord-bridge.service -f` or `tail -f pi-app/var/app.log`).

## 6. Tips
- Metadata JSON is optional but useful if you want to flag the source (e.g.,
  `{"source":"expo","note":"kids hoodies"}`).
- Draft numbers are clickable; tapping opens the Pi draft page in your phone’s
  browser for quick edits.
- Expo caches assets; run `npm run clean` or delete `.expo/` if images appear
  stale after large changes.
- When you’re done testing press `Ctrl+C` in the Expo terminal to stop the
  bundler/tunnel.

Need help? Ping `@codex` in Discord with the draft number and any screenshot/log.
