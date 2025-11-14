# Agent Relay (Codex ↔ Codex chat)

Sometimes both Codex agents run in parallel (e.g., CLI + Discord bridge). To
keep coordination off your plate, the Pi now hosts a minimal message bus in
`.agent/relay/`.

## CLI

`tools/agent_relay.py` exposes two commands:

```bash
# send a note from the CLI agent to the Discord-side agent
python tools/agent_relay.py send --author codex-cli --target codex-discord "Need the new bot token?"

# pull unread messages for the Discord-side agent (and clear them)
python tools/agent_relay.py pull --agent codex-discord --mark-read
```

Messages are appended to `.agent/relay/log.jsonl` for historical auditing and
buffered per-recipient under `.agent/relay/inbox-<agent>.jsonl`. Using
`--mark-read` truncates the corresponding inbox so future pulls only return new
entries. Add `--limit N` to only see the most recent N messages (useful when an
inbox is large).

### Broadcast

If you ever add a third agent, `--broadcast` fans the same entry out to every
known inbox:

```bash
python tools/agent_relay.py send --author codex-cli --target codex-all --broadcast "Samper run kicked off."
```

The `target` value is still stored on the message for context even though each
agent gets a copy.

## Where to read/write

```
.agent/relay/
├── log.jsonl              # immutable history (all messages)
├── inbox-codex-cli.jsonl  # per-agent queue (one file per agent id)
├── inbox-codex-discord.jsonl
└── ...
```

Feel free to version-control these inbox files when context matters (or delete
them once chats become stale). Since everything is plain JSON, it’s easy to tail
with `jq` or plug into richer tooling later.

## Mirror relay chatter to Discord

Set a webhook URL (e.g., the dedicated “agent-chatter” channel you created) to
mirror every message automatically:

```bash
export AGENT_RELAY_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

Every send action posts a short embed summarising `author → target: message`. You
can override per message with `--webhook <url>` if you want to tee a specific
thread to a different channel.

## Push-style listeners (no manual pulling)

Run the stream helper so an agent gets messages automatically:

```bash
python tools/agent_relay_stream.py --agent codex-discord
```

That drains `.agent/relay/inbox-codex-discord.jsonl` in FIFO order and prints new
messages as soon as they arrive (default poll: 1s). Add hooks:

```bash
# Pipe JSON payload into a handler script
python tools/agent_relay_stream.py --agent codex-discord --exec 'python agent_handler.py'

# Push every entry to an HTTP listener
python tools/agent_relay_stream.py --agent codex-discord --http http://127.0.0.1:4040/relay
```

The streamer acknowledges (removes) messages after delivery; use `--no-ack` to
leave them intact if you need multiple consumers.

### Systemd helper

Deploy always-on listeners per agent with the templated unit:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/systemd/agent-relay@.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now agent-relay@codex-discord.service
```

Override the `ExecStart` via a drop-in if you need custom `--exec`/`--http`
arguments.
