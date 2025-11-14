# Granting Pi Access to a New Agent

Use this checklist whenever we onboard another Codex agent (or human) who needs
shell access to the Raspberry Pi.

## 1. Generate an SSH key (agent side)
Ask the new agent to run on **their** machine:

```bash
ssh-keygen -t ed25519 -C "agent-name"
# save the key (e.g., ~/.ssh/codex-agent)
cat ~/.ssh/codex-agent.pub
```

They should send you the **public** key (the `.pub` file only).

## 2. Add the key on the Pi
On the Pi (logged in as `pi`):

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
nano ~/.ssh/authorized_keys
```

Paste the agent’s public key on a new line (keep existing keys). Save, then:

```bash
chmod 600 ~/.ssh/authorized_keys
```

If you want the agent to log in as a different user (e.g., `vinted`), repeat the
same steps in that user’s home directory.

## 3. Share connection details
Send the agent:
- Hostname/IP (e.g., `ssh pi@100.85.116.21`)
- Optional: which environment variables or secrets file to source (e.g., `source ~/vinted-ai-cloud/.venv/bin/activate`).

## 4. Verify
Ask the agent to run:
```bash
ssh -i ~/.ssh/codex-agent pi@100.85.116.21 'hostname && uptime'
```
If that succeeds, they have the same access level as the existing CLI agent.

## 5. Environment setup (recommended)
Once connected, they should:
```bash
cd ~/vinted-ai-cloud
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```
This ensures Playwright/cloudscraper/etc. are available on the Pi if they need
to run scripts locally.

## 6. Revoke/rotate access
To remove an agent, delete their public key line from `~/.ssh/authorized_keys`.
For compromised keys, remove the line and ask them to regenerate a new pair.

---
**Note:** I can’t add keys automatically without the agent’s public key, so I’m
not a “super user” in the sense of creating credentials on my own. As soon as you
provide a new `.pub` entry, I can append it to `authorized_keys` for you if
that’s easier—just drop the key into `~/secrets/new-agent.pub` and let me know.
