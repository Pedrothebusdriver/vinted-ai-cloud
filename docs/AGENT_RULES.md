# Agent Rules – How to Behave in This Repo

This repo belongs to Pete. Pete is a beginner with ADHD and many projects.  
Your job as an agent is to **reduce** his cognitive load, not increase it.

## 1. Always read the shared context first

On each new session:
1. Read or re-read:
   - `docs/fliplens_prd.md`
   - `docs/actions_for_pete.md`
   - `docs/AGENTS.md`
   - `docs/AGENT_RULES.md`
2. Decide which role you are acting as:
   - AGENT_CORE, AGENT_MOBILE, AGENT_OPS, or AGENT_QA.
3. From `docs/actions_for_pete.md`, pick the highest-priority unfinished task that matches your role.

Do **not** ask Pete “what next?” if the next task is already written down.

## 2. Default workflow for any task

For each task you pick:

1. Restate the task in your own words (in the console).
2. Find the relevant code and docs.
3. Make a **small, coherent** set of changes focused on that task.
4. Run appropriate checks:
   - For backend: relevant tests or at least syntax/import checks.
5. Update docs if needed (PRD or actions, when behaviour changes).
6. Commit and push:
   - Use clear messages like `feat: add ingest skeleton` or `fix: stabilise /api/drafts`.

Only ask for human input if:
- You hit a blocker you cannot resolve after reasonable attempts.
- The task is ambiguous in the docs.
- The change would be risky (e.g. deleting a lot of code or touching personal system config).

## 3. Git & collaboration

- Before committing:
  - Run `git status` and `git diff` to see what changed.
  - If the branch moved, `git pull --rebase` and resolve small conflicts.
- Never `git push --force` unless the task explicitly says so.
- Don’t delete unrelated files “for cleanliness” without a clear reason in the actions doc.

## 4. Scope & safety boundaries

- Stay within this repo and its documented purpose.
- Do NOT:
  - Implement bot-like automatic posting to Vinted for normal users.
  - Try to log in to Vinted accounts.
- FlipLens MVP is:
  - Draft creation
  - Assisted posting (clipboard + instructions)

Future Vinted Pro integrations will be explicitly scoped later.

## 5. How to report when you’re done

When you finish a unit of work:
- Print a short summary:
  - Which task you did.
  - Which files you touched.
  - Which checks/tests you ran and results.
  - Any follow-up tasks you noticed.
- If you added tasks, append them to `docs/actions_for_pete.md` in a clear, numbered way.

Assume autonomy by default.  
Pete will review GitHub and logs when he has time.
