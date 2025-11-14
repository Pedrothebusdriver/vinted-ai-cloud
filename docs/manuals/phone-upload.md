# Phone Upload Guide (Step-by-Step)

This guide walks you (in very simple steps) through sending photos from your
phone to the Pi so it builds a Vinted-ready draft and posts the result in
Discord. No coding required.

## What you need
- iPhone with the **Shortcuts** app (installed by default).
- Internet access to reach `http://100.85.116.21:8080`.
- The Discord server where drafts get posted (e.g., “AI Test”).
- Upload API key string (ask the team; needed any time `/api/upload` is public).

## One-time setup
1. Open the **Shortcuts** app on your iPhone.
2. Tap the **+** button (top right) to create a new shortcut.
3. Name it something easy, like `Send to Vinted Pi`.
4. Add the following actions in order (you can search for each action at the
   bottom of the screen):
   1. **Select Photos**
      - Tap the action → toggle **Select Multiple** ON.
   2. **Repeat with Each** (Shortcuts adds this automatically after Select Photos).
   3. Inside the Repeat, add **Get Contents of URL**:
      - Tap **URL** and enter `http://100.85.116.21:8080/api/upload`.
      - Tap **Method** and choose **POST**.
      - Tap **Request Body** → select **Form**.
      - Tap **Add New Field** → choose **File**.
        - Name: `files`
        - File: tap **Choose** → pick **Repeat Item** (the current photo).
      - OPTIONAL: add another field named `metadata`.
        - Type: **Text**
        - Value: e.g., `{"source":"iphone-shortcut","note":"Bedroom hoodie"}`
      - Tap **Headers** → **Add New Field**.
        - Key: `X-Upload-Key`
        - Value: (paste your upload API key; Shortcuts stores it on-device).
   4. After the POST action, add **Get Dictionary from Input** (this parses the
      server response).
   5. Add **Show Notification** with the text:
      - `Draft queued: #${Dictionary["item_id"]}`
5. Tap **Done** to save the shortcut.

## Using the shortcut
1. Open **Shortcuts** and tap `Send to Vinted Pi`.
2. Pick the photos of the item you want to list (select all angles/labels).
3. Tap **Add** (top right). The shortcut uploads each photo, one by one.
4. You’ll see a notification like `Draft queued: #31`.
5. Check Discord (e.g., `#vinted-bot` channel). Within ~1 minute you should see:
   - A thumbnail + summary (brand/size/colour/type).
   - A link like `http://100.85.116.21:8080/draft/31`.
6. Tap the link on your phone to view/edit the draft. Make any tweaks (title,
   brand, size) and hit **Save**.

## Tips
- If the upload fails, Shortcuts will show an error. Run it again and make sure
  you’re connected to Wi-Fi/cellular.
- You can duplicate the shortcut and change the `metadata` text for different
templates (e.g., `"note":"Kids jackets"`).
- Draft links always open in Safari and work fine on mobile.
- If Shortcuts says “401 unauthorized,” double-check the `X-Upload-Key` header
  or request a new key.

Need help? Ping `@codex` in Discord and mention the draft number.
