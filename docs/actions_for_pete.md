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
3. Confirm whether the PI will continue to run on your home IP or move to the mini PC so we point the app + web form at the right host.
4. We will configure the Pi service to require `X-Upload-Key: <value>` and update the Shortcut/Web forms accordingly.

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

## 5. Provide SSH Keys for New Agents
**Goal:** give additional agents the same Pi access as the primary CLI.**

1. Follow the guide in `docs/manuals/pi-access.md`.
2. Ask each new agent for their public key (`.pub` file only).
3. Either add it yourself (per the guide) or drop the `.pub` file on the Pi (e.g., `~/secrets/new-agent.pub`) and tell me to append it.
4. Let the agent test `ssh pi@100.85.116.21` so they can run scripts without waiting for me.

---

## 6. Hardware Platform Preference
**Goal:** pick the next machine (Intel N100 vs. Ryzen mini PC vs. other) so we can start provisioning.

1. Skim `docs/hardware_security.md` for the short-list + provisioning plan.
2. Let us know which direction you prefer (cheap N100 now vs. higher-end Ryzen/Jetson) and your budget/availability constraints.
3. If you already have a candidate model in mind, drop the link/specs here so we can tailor the Ansible/provisioning scripts to that hardware profile.

Once we have your choice, we’ll script the install + benchmarking flow and prep the migration steps.

---

## 7. Replace Agent 3 (lacks Pi access)
**Goal:** onboard a new agent with proper SSH access since the current “Agent 3” cannot run terminal commands.**

1. Collect the new agent’s SSH public key (run `ssh-keygen -t ed25519 -C "agent3"` and send the `.pub`).
2. Add it to the Pi per `docs/manuals/pi-access.md` (or drop the `.pub` on the Pi and ask us to append it).
3. Share the connection command (`ssh -i ~/.ssh/agent3_key pi@100.85.116.21`) and remind them to set up the repo/venv.

Once the replacement agent confirms they can run commands, mark this item done and archive the old agent’s key if needed.

---

## 8. Re-authorize Discord Bridge Bot
**Goal:** refresh the bot’s permissions so it can actually send messages again.**

1. In the Discord Developer Portal → Bot tab, tick `View Channel`, `Send Messages`, `Read Message History`, `Attach Files` (and any other text perms you want).
2. Go to **OAuth2 → URL Generator**, select `bot` scope + the same permissions, copy the generated URL, and open it to re-add the bot to your server.
3. Confirm in Server Settings → Integrations → Bot that those permissions show as green checks.
4. Ping us so we can restart the bridge services and verify replies land in Discord.

---

## 9. Discord Bridge Go-Live
**Goal:** get the shared Discord ↔︎ Codex bridge online so all agents (CLI + Discord) can coordinate in one channel.

1. Finalize the bot token + channel IDs (see item #1) and confirm which Discord channel(s) we should mirror.
   - Status: token stored under `~/secrets/discord_bot.json`; channel `#vinted-ai-group-chat` (ID `1438888366832746517`) is ready.
2. Confirm whether the bridge should post as a standalone bot user or via webhooks (affects how we brand the messages). _Default: bot user._
3. Give a thumbs-up when you’re ready for us to deploy `tools/discord_bridge_bot.py` on the Pi/mini PC; we’ll set up the systemd unit and test both inbound/outbound paths. _Ready once you confirm the bot should post under its own name._

Once you’re good with those, we’ll light it up so you, the other agents, and the CLI can chat in real time.

---

## 7. Discord Role/Channel Access
**Goal:** (Future) allow the bridge bot (or agent accounts) to create/delete/manage channels when we need to tidy Discord.

1. When ready, create a server role (e.g., `AI Admin`) with the permissions you’re comfortable delegating (Manage Channels, View Channels, etc.).
2. Assign that role to the bot user (or specific agent accounts).
3. Update this doc with any guardrails (“don’t touch private staff channels,” etc.) so we know the scope when you flip the switch.

This can wait until you want us to handle more Discord upkeep; just keeping it on the radar.

---

## 8. Dedicated Agent Bots (Future)
**Goal:** give each agent its own Discord bot/user so messages show up under unique names (no prefixes needed).

1. When/if we want this, we’ll need one Discord application per agent (each with its own token).
2. We can either run multiple instances of the bridge bot (one per agent) or extend the existing bot to support per-agent personas.
3. Note down any naming scheme you prefer so we can reserve bot usernames ahead of time.

For now the shared bot + `[Agent#X]` prefixes work; this item is just to revisit when we want individual presences.

---

Add more items here if you (or another agent) need new inputs from Pete. Keep the instructions simple so anyone can follow them.
