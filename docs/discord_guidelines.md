# Discord Usage Guidelines – FlipLens

Discord is our lightweight command centre for FlipLens: agents post run logs, ingest alerts, and coordination notes there so Pete can glance at system health without reading console output.

## Channel priorities
- **High-priority (keep unmuted):** channels that surface alerts/errors (`#alerts-agent`, `#ops-triage`, etc.), deploy notes, and human coordination threads.
- **Lower-priority (optional mute):** noisy debug streams (`#agent-debug`, `#pi-console`), experimental multi-agent chatter, or archive/legacy channels.

## ADHD-friendly daily routine
1. Morning (2–3 min): Check the alerts channel for overnight errors. If clear, skim `#status-updates` for any summaries.
2. Midday (quick scan): Peek at the ops/deploy channel if you’re about to ship something – make sure no one else is performing maintenance.
3. Evening wrap-up: Clear any unread alerts; if something needs human follow-up, note it in `docs/actions_for_pete.md`.

## Follow-up to enable Discord access
- The bridge can’t post yet because we haven’t configured a bot token. Follow the steps in `docs/discord_channels_review.md` (“Follow-up to enable Discord access” + “Getting the bridge online”) to wire up credentials. Once the bot is connected, update the channel table there with real names/IDs.
