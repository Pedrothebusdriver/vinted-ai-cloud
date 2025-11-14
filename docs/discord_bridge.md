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
3. **Create a secrets file (recommended)**
   ```bash
   mkdir -p ~/secrets && chmod 700 ~/secrets
   cat <<'JSON' >~/secrets/discord_bot.json
   {
     "token": "BOT_TOKEN_HERE",
     "channel_ids": ["123456789012345678"],
     "allowed_user_ids": [],
     "forward_url": null,
     "forward_token": null
   }
   JSON
   ```
   - `channel_ids` accepts one or more numeric Discord channel IDs.
   - You can still override anything via env vars later if needed.
4. **Configure env**
   Add the following to `pi-app/.env` (or any file sourced before starting the
   bot):
   ```bash
   export DISCORD_BRIDGE_CONFIG="${HOME}/secrets/discord_bot.json"
   # optional overrides:
   # export DISCORD_BRIDGE_TOKEN="..."                 # override token from JSON
   # export DISCORD_BRIDGE_CHANNELS="123,456"          # override channels
   # export DISCORD_BRIDGE_ALLOW_USERS="1234,5678"     # whitelist user IDs
   # export DISCORD_BRIDGE_FORWARD_URL="http://..."    # webhook forward target
   # export DISCORD_BRIDGE_FORWARD_TOKEN="secret"
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
.venv/bin/python tools/discord_bridge_send.py --sender "Agent#1" "Ship it 🚀"
# or reply to a specific message id (copy jump_url → ID)
.venv/bin/python tools/discord_bridge_send.py --sender "Agent#1" --reply-to 1187349871234 "On it."
```

The bridge bot polls `.agent/discord-bridge/outbox/` every ~2 seconds, posts the
message to Discord, then moves the payload into `.agent/discord-bridge/sent/`
(or `.agent/discord-bridge/failed/` on errors).

Tips:

- Set `DISCORD_BRIDGE_SENDER=Agent#1` in your shell if you don’t want to pass
  `--sender` every time. The value becomes the prefix (`[Agent#1] …`) that shows
  up in Discord.
- Attachments can be added via `--file path/to/screenshot.png` (repeat the flag
  to attach multiple files).

## Optional: systemd units

Copy the sample units to keep everything alive on the Pi:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/systemd/discord-bridge.service ~/.config/systemd/user/
cp scripts/systemd/discord-bridge-relay.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now discord-bridge.service
systemctl --user enable --now discord-bridge-relay.service
```

The service assumes the repo lives at `~/vinted-ai-cloud` and that the Python
venv is `pi-app/.venv`. Adjust the unit file if your paths differ.

Check logs with:

```bash
journalctl --user -u discord-bridge.service -f
journalctl --user -u discord-bridge-relay.service -f
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

## Relay integration (push Discord → every agent)

`tools/discord_bridge_relay.py` watches the Discord inbox and writes new entries
into `.agent/relay/` so each agent’s inbox gets the same message automatically.

### Quick check (manual)

```bash
.venv/bin/python tools/discord_bridge_relay.py --agents codex-cli,codex-discord
```

Add `--loop` to keep it running in the foreground. When ready for 24/7
operation, use one of the options below.

### Option A: systemd on the Pi

```bash
mkdir -p ~/.config/systemd/user
cp scripts/systemd/discord-bridge-relay.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now discord-bridge-relay.service
journalctl --user -u discord-bridge-relay.service -f
```

The service reads the same env file as the main bridge and automatically
restarts on failure.

### Option B: macOS LaunchAgent (per agent)

Create a plist similar to:

```bash
cat <<'EOF' > ~/Library/LaunchAgents/com.codex.agent-relay-cli.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>com.codex.agent-relay-cli</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/you/vinted-ai-cloud/tools/agent_relay_stream.py</string>
        <string>--agent</string><string>codex-cli</string>
        <string>--interval</string><string>10</string>
        <string>--quiet</string>
    </array>
    <key>WorkingDirectory</key><string>/Users/you/vinted-ai-cloud</string>
    <key>StandardOutPath</key><string>/tmp/relay-codex-cli.log</string>
    <key>StandardErrorPath</key><string>/tmp/relay-codex-cli.err</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
</dict>
</plist>
EOF

launchctl unload ~/Library/LaunchAgents/com.codex.agent-relay-cli.plist >/dev/null 2>&1 || true
launchctl load ~/Library/LaunchAgents/com.codex.agent-relay-cli.plist
```

Duplicate the plist (change the label + `--agent` flag) for `codex-discord` or
any other inbox you want to keep in sync on your Mac.

### Option C: agent-relay@ systemd template

There’s also a generic unit (`scripts/systemd/agent-relay@.service`) if you
want one per agent on the Pi:

```bash
cp scripts/systemd/agent-relay@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agent-relay@codex-cli.service
systemctl --user enable --now agent-relay@codex-discord.service
```

Each instance runs `tools/agent_relay_stream.py --agent <name>` so messages are
drained without manual pulls.

### Suggested naming convention

- Give each agent a consistent relay inbox (`codex-cli`, `codex-discord`, `codex-hardware`, …).
- Set `DISCORD_BRIDGE_SENDER=Agent#1` (or similar) in each agent’s env so replies
  show up in Discord as `[Agent#1] message`, making it obvious who spoke.

## Agent quick-start

1. **Receive messages**  
   ```bash
   python tools/agent_relay.py pull --agent codex-cli --mark-read
   ```
   (Replace `codex-cli` with your relay inbox name.) You’ll see Discord posts in
   the format `[Discord:DisplayName] message`.

2. **Reply**  
   ```bash
   export DISCORD_BRIDGE_SENDER="Agent#1"   # run once per shell
   python tools/discord_bridge_send.py "On it."
   ```
   The bot posts `[Agent#1] On it.` back into the Discord channel. Use
   `--file` to attach screenshots.

3. **Keep the service running**  
   Ensure both `discord-bridge.service` and `discord-bridge-relay.service` are
   enabled via systemd so inbound/outbound flows stay live without manual
   intervention.

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
