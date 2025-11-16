# Agent Naming & Systemd Instructions

We need to give each background agent a clear name (“Agent 1/2/3”) so it’s obvious who is doing what and so systemd logs stay readable. Follow this when setting up or renaming agents on the Pi.

## 1. Decide the names and commands
For each long-running agent, write down:
- Desired label (e.g., `Agent1`, `Agent2`, `Agent3`).
- The exact command it should run.

Example mapping:
| Label   | Command |
|---------|---------|
| Agent1  | `/home/pi/vinted-ai-cloud/.venv/bin/python tools/playwright_sampler.py --whatever` |
| Agent2  | `/home/pi/vinted-ai-cloud/.venv/bin/python tools/agent_relay_stream.py --agent agent2 --interval 1` |
| Agent3  | `/home/pi/vinted-ai-cloud/.venv/bin/python tools/agent_relay_stream.py --agent agent3 --interval 1` |

## 2. Stop the old instance (if running)
If an un-named instance is already running, stop it first so we don’t duplicate work:
```bash
systemctl --user stop agent-relay@codex-cli.service   # example
systemctl --user disable agent-relay@codex-cli.service
```
Only stop an agent when it’s safe (e.g., after a sampler batch finishes).

## 3. Start the new named service
Use the `agent-relay@.service` template (already installed on the Pi) so the name shows up everywhere:
```bash
systemctl --user enable --now agent-relay@Agent2.service
```
This runs:
```
/home/pi/vinted-ai-cloud/.venv/bin/python tools/agent_relay_stream.py --agent Agent2 --interval 1
```
Whatever you put after the `@` becomes the agent name and the `--agent` flag automatically.

For non-relay jobs (e.g., Playwright sampler), create a dedicated service file under `~/vinted-ai-cloud/scripts/systemd/` (e.g., `playwright-agent1.service`) with the correct `ExecStart`, copy it into `~/.config/systemd/user/`, then enable it:
```bash
systemctl --user enable --now playwright-agent1.service
```

## 4. Verify
Check each service:
```bash
systemctl --user status agent-relay@Agent2.service
journalctl --user -u agent-relay@Agent2.service -f
```
Make sure logs show the new name (“Agent2”) so we know the mapping worked.

## 5. Update the tracker
Keep `docs/actions_for_pete.md` (or a shared tracker) updated with who is Agent1/2/3 and what command they’re running so nobody overwrites another agent’s job.

---
---
## Summary for Agent 1 (Playwright)
- Pete is rebooting his Mac; all persistent agents now run on the **Pi via systemd** (relay, bridge, etc.).
- Playwright sampler is still being run manually while the multi-photo parser is finished. Command is:
  ```bash
  source ~/.venv/bin/activate
  python tools/playwright_sampler.py --terms hoodie --upload --use-cloudscraper
  ```
- Once the sampler is stable (after the carousel extraction is complete), Codex will ping the team so it can be wrapped in a service `playwright-agent1.service` and labelled **Agent1**.
- Until that handoff happens, keep the relay services named `Agent2`/`Agent3` but expect Agent1 naming to arrive with the Playwright service.
