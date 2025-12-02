# Self-play pipeline

Utilities for generating self-play data without relying on the production stack. The flow:

1. Scrape (or synthesize) Vinted-style listings into `tools/selfplay/data/scraped_listings.jsonl`.
2. Run a self-play round to produce prediction and correction logs under `tools/marketplace_eval/data/`.
3. Run the evaluation harness to include the self-play stats in the report.

Example commands (from repo root):

```bash
source .venv/bin/activate
python tools/selfplay/scrape_vinted_listings.py --max-listings 25
python tools/selfplay/run_selfplay_round.py --max-examples 25
python tools/marketplace_eval/run_eval.py
```

Use `--dry-run` on the scraper to skip writing files while previewing fetched data.
