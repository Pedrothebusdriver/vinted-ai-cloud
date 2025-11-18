# AGENT RULES – Vinted AI Cloud / FlipLens

These rules apply to **all agents** working in this repository.

The main goal right now is to deliver the **FlipLens MVP** as described in `docs/fliplens_prd.md`, using the tasks tracked in `docs/actions_for_pete.md`.

---

## 1. Always read the shared documents first

On startup, every agent must:

1. Read:
   - `docs/fliplens_prd.md`
   - `docs/actions_for_pete.md`
   - `docs/AGENTS.md`
   - `docs/AGENT_RULES.md`
2. Identify:
   - Current milestones and tasks relevant to its own role.
   - Tasks that are already done vs still open.

Agents should not ask the user to restate the project goals – they live in these docs.

---

## 2. Scope and priorities

1. Primary focus:
   - FlipLens MVP (Vinted listing assistant for home sellers).
   - Underlying “Vinted AI Core” on the Pi.
2. Secondary / parked:
   - Discord multi-agent relay.
   - CharityLoop client.
   - Vinted Pro API integration.

Agents must **not** start work on secondary items unless:
- The primary milestone for FlipLens is complete, or
- `docs/actions_for_pete.md` explicitly lists a secondary task as “Next”.

---

## 3. Autonomy vs stopping points

Agents should:

- **Be proactive**:
  - Pick the next task that matches their role from `docs/actions_for_pete.md`.
  - Break big tasks into smaller sub-steps.
  - Execute them without asking for per-task human approval.

- **Stop and ask for human input** when:
  - A change requires destructive action outside this repo or the Pi project.
  - A design decision is ambiguous and not covered by `fliplens_prd.md`.
  - Deploying or restarting critical services on the Pi (`ssh pi-vinted`) if not explicitly requested.

Rule of thumb: small refactors and internal changes are fine to do autonomously. Anything that might surprise Pete in a scary way should be paused and surfaced.

---

## 4. Git and change hygiene

1. Keep commits **small and focused**.
2. Prefer commit messages like:
   - `feat(core): scaffold ingest module`
   - `feat(api): add /api/drafts endpoint`
   - `chore(docs): update actions for milestone 1`
3. Before committing:
   - Run relevant tests (`pytest`, unit tests for affected modules).
   - Ensure the code at least imports cleanly.
4. Avoid force pushes unless there is a very strong reason, and never without mentioning it explicitly in the conversation.

---

## 5. Coordination via docs

Agents coordinate using the docs instead of constantly asking Pete:

- `docs/actions_for_pete.md`:
  - The **single source of truth** for what is next.
  - The PM/Planner agent is responsible for keeping it tidy.
- `docs/STATUS.md`:
  - Maintained primarily by the Status / Pete Helper agent.
  - Contains a human-readable summary of recent work plus a “Ready for Pete to test” section with concrete commands.

When an agent completes a task:
- Update `docs/actions_for_pete.md`:
  - Mark the item as done or move it to a “Done” section.
- Optionally add a brief note to `docs/STATUS.md`.

---

## 6. Pi and external systems

- The Pi is reachable via `ssh pi-vinted`.
- Agents may:
  - Use `ssh pi-vinted` to inspect logs, check services, or run safe commands **if a task explicitly calls for it**.
- Agents must **not**:
  - Reboot the Pi.
  - Delete large directories.
  - Change system-wide configuration files.

Any potentially dangerous command on the Pi should be explained before being run so Pete can review.

---

## 7. Boundaries

- Stay inside this project unless told otherwise.
- Do not modify unrelated repositories.
- Do not automate interactions with Vinted in ways that violate their terms of service. For FlipLens MVP, the product focuses on draft generation and assisted posting, not headless browser automation.

---

## 8. When in doubt

If there is a genuine conflict between:
- What the code currently does,
- What `docs/fliplens_prd.md` says, and
- What seems safe,

then:
1. Prefer to align with `docs/fliplens_prd.md`.
2. Leave the existing behaviour in place behind a feature flag or config if needed.
3. Add a short note to `docs/STATUS.md` and ask Pete for a decision in the chat.
