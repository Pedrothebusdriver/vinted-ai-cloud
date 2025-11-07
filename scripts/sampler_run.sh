name: Sampler (Openverse) — Download & Report

on:
  workflow_dispatch: {}
  repository_dispatch:
    types: [run-sampler]

jobs:
  sampler:
    runs-on: [self-hosted, pi]
    timeout-minutes: 20
    env:
      DISCORD_AGENT_WEBHOOK: ${{ secrets.DISCORD_AGENT_WEBHOOK }}  # images+results channel
      PI_INFER_URL: ${{ vars.PI_INFER_URL }}                       # e.g. http://127.0.0.1:8080/api/infer
    steps:
      - name: Checkout (no built-in creds)
        uses: actions/checkout@v4
        with:
          persist-credentials: false
          fetch-depth: 0

      - name: Configure git
        run: |
          git config user.name  "${{ secrets.GH_AGENT_NAME || 'pi-agent' }}"
          git config user.email "${{ secrets.GH_AGENT_EMAIL || 'pi@local' }}"

      - name: Download images on the Pi
        run: bash scripts/sampler_run.sh

      - name: Evaluate & post to Discord
        run: |
          if [ -f tools/eval_report.py ]; then
            python3 tools/eval_report.py
          else
            echo "Missing tools/eval_report.py — skipping eval post."
          fi

      - name: Commit summary + eval results (no images)
        run: |
          git add .agent/sampler/summary-*.json || true
          git add data/evals || true
          if git diff --cached --quiet; then
            echo "No artifacts to commit."
          else
            git commit -m "sampler/eval: artifacts $(date -u +%Y-%m-%dT%H:%M:%SZ)"
            git log -1 --name-only
          fi

      - name: Push using PAT
        env:
          GH_PAT: ${{ secrets.GH_AGENT_PAT }}
        run: |
          git push "https://x-access-token:${GH_PAT}@github.com/${{ github.repository }}.git" HEAD:main
          echo "PUSHED OK (or up-to-date)"
