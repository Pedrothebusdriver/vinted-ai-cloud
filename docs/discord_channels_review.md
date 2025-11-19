# Discord Channels Review – FlipLens Agents

The Discord bridge code already exists in this repo, but no bot token or credentials have been configured yet. That means the agents cannot currently post updates or alerts to Discord – wiring up access is the next step.

## Follow-up to enable Discord access

1. **Create a Discord bot + token** via the Discord Developer Portal and invite it to the FlipLens server with the required channel permissions (read/send messages).
2. **Store the token securely**:
   - The bridge scripts under `tools/` expect a `.env` or environment variables. Add a `.env.discord` (never checked in) with `DISCORD_BOT_TOKEN=...` and, if applicable, `DISCORD_GUILD_ID` / `DISCORD_CHANNEL_ID_ALERTS` / `DISCORD_CHANNEL_ID_LOGS`.
   - Alternatively, export these variables before running the bridge: `export DISCORD_BOT_TOKEN=...` etc.
3. **Configure runtime options**:
   - Check `tools/discord_bridge.py` (or the relevant script) for additional settings like webhook URLs or channel mappings.
   - Document the channel names + IDs in `docs/discord_channels_review.md` once confirmed.
4. **Secrets management**:
   - On the Pi or deployment host, place the `.env.discord` file alongside the FastAPI `.env` and load it via `source` before starting the bridge.

## Proposed channel status table (examples)
| Channel | Status | Notes |
| --- | --- | --- |
| `#alerts-agent` *(placeholder)* | ACTIVE | Real-time errors from ingest, pricing, compliance. Should remain noisy. |
| `#ops-triage` *(placeholder)* | ACTIVE | Manual interventions + deploy notes. |
| `#agent-debug` *(placeholder)* | LEGACY | Old multi-agent relay spam; safe to mute once new bridge is live. |
| `#status-updates` *(placeholder)* | STALE | Automated status posts last updated weeks ago; review before reusing. |

*(Replace placeholders with actual channel names/IDs once the bot has access.)*

## Getting the bridge online

1. Install dependencies: `pip install -r requirements.txt` (or the specific `discord.py` version used).
2. Ensure the `.env.discord` variables are exported in the shell (e.g., `source .env.discord`).
3. Run the bridge script:
   ```bash
   cd tools
   python discord_bridge.py --channels alerts-agent,ops-triage
   ```
4. Keep the process running via `systemd` or `tmux` on the Pi so alerts flow continuously.
5. Verify the bot joins the target channels and can send a test message.

If the bridge uses Node or additional tooling, follow the README in `tools/` to install those dependencies before step 3.
