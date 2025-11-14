# Discord Bridge Bot

Stay in touch with Codex while you're away from the Mac. The bridge bot runs
on the Pi (or any always-on box), listens for Discord messages, and mirrors
them to the repo so Codex can pick them up during the next CLI session. It
also lets Codex reply back into Discord without leaving the terminal.

## Features

- Watches one or more Discord channels for new messages.
- Stores every inbound payload under `.agent/discord-bridge/inbox/` as both
  prettified JSON and JSONL history (attachments optionally downloaded).
- Optionally forwards each payload to an HTTP endpoint (e.g., a webhook that
  pings Codex instantly).
- Polls `.agent/discord-bridge/outbox/` for replies created via
  `tools/discord_bridge_send.py` and posts them back to Discord.
- Simple file-based contract means you can version-control conversations or
  script additional automations.

## Setup

1. **Create a Discord bot**
   - Visit <https://discord.com/developers/applications>.
   - Create a bot, copy the token, and invite it to your server with
     `Send Messages`, `Read Message History`, and `Message Content` intents.
2. **Install dependencies**
   ```bash
   cd ~/vinted-ai-cloud
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Configure env**
   Add the following to `pi-app/.env` (or any file sourced before starting the
   bot):
   ```bash
   export DISCORD_BRIDGE_TOKEN="bot-token-here"
   export DISCORD_BRIDGE_CHANNELS="123456789012345678,987654321098765432"
   # optional:
   # export DISCORD_BRIDGE_ALLOW_USERS="1234,5678"   # whitelist user IDs
   # export DISCORD_BRIDGE_FORWARD_URL="http://127.0.0.1:4040/agent/inbox"
   # export DISCORD_BRIDGE_FORWARD_TOKEN="secret"    # bearer token for forward URL
   ```
4. **Run the bot**
   ```bash
   source pi-app/.env
   .venv/bin/python tools/discord_bridge_bot.py
   ```

You should see `Bridge ready as ...` in the logs. Messages from the configured
channels will start populating `.agent/discord-bridge/inbox/`.

## Sending replies from the CLI

Use the helper script to queue a reply:

```bash
.venv/bin/python tools/discord_bridge_send.py "Ship it 🚀"
# or reply to a specific message id
.venv/bin/python tools/discord_bridge_send.py --reply-to 1187349871234 "On it."
```

The bridge bot polls `.agent/discord-bridge/outbox/` every ~2 seconds, posts the
message to Discord, then moves the payload into `.agent/discord-bridge/sent/`
(or `.agent/discord-bridge/failed/` on errors).

Attachments can be added via `--file path/to/screenshot.png`.

## Optional: systemd unit

Copy the sample unit to keep the bot alive on the Pi:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/systemd/discord-bridge.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now discord-bridge.service
```

The service assumes the repo lives at `~/vinted-ai-cloud` and that the Python
venv is `pi-app/.venv`. Adjust the unit file if your paths differ.

Check logs with:

```bash
journalctl --user -u discord-bridge.service -f
```

## Consuming messages

Codex (or any automation) can now watch `.agent/discord-bridge/inbox/messages.jsonl`
for new payloads. Each entry includes:

- `author` info
- `content` (raw + clean)
- `attachments` (local path + original URL where available)
- `jump_url` back to the Discord message

If you set `DISCORD_BRIDGE_FORWARD_URL`, the same payload is POSTed to that URL
in real time so you can trigger push notifications, queue Jenkins jobs, etc.

## Directory layout

```
.agent/discord-bridge/
├── inbox/          # inbound messages + latest.json + messages.jsonl
├── outbox/         # drop replies here (processed files move after send)
├── sent/           # successful outbound payloads
├── failed/         # payloads we couldn't send
└── media/          # downloaded attachments (if enabled)
```

Prune older media/history as needed; nothing else depends on them.
