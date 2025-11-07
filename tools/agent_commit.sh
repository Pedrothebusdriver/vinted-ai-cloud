#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-$HOME/vinted-ai-cloud}"
MSG="${2:-agent: automated update}"
cd "$REPO"

BR="agent/$(date +%Y%m%d-%H%M%S)"
git switch -c "$BR" >/dev/null 2>&1 || git checkout -b "$BR"

git add -A
if git diff --cached --quiet; then
  echo "[agent_commit] nothing to commit"; exit 0
fi

git -c user.name='pi-agent' -c user.email='pi@local' commit -m "$MSG"
git push -u origin "$BR"

if command -v gh >/dev/null; then
  gh pr create --title "$MSG" --body "Automated PR from Pi agent." --fill || true
else
  echo "[agent_commit] install 'gh' for auto-PR: sudo apt-get install -y gh && echo \$GITHUB_PAT | gh auth login --with-token"
fi
