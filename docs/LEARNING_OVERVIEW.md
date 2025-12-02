# Learning Loop (Teacher → Student)

This repo now supports an offline teacher–student loop in GBP so we can learn from both self-play and real user edits without touching the upload flow.

## Data sources
- **Teacher (ground truth)**: `tools/selfplay/data/scraped_listings.jsonl` (scraped or placeholder, GBP-only).
- **Student predictions**: produced by the heuristics in `inference_core.py` using `auto_heuristics_config.json`.
- **Logs**: written to `tools/marketplace_eval/data/` as JSONL
  - `selfplay_predictions.jsonl`, `selfplay_corrections.jsonl`
  - `user_predictions.jsonl`, `user_corrections.jsonl` (from the app)

## How the loop runs
1) **Scrape or synthesise listings** (teacher data)  
   `python tools/selfplay/scrape_vinted_listings.py --max-listings 25`
2) **Generate student guesses vs truth**  
   `python tools/selfplay/run_selfplay_round.py --max-examples 25`
   - Writes paired prediction/correction logs in GBP.
3) **Learn from corrections** (user + self-play)  
   `python tools/auto_learn.py`  
   - Adjusts GBP price bands in `auto_heuristics_config.json` when a consistent bias is observed.
4) **Evaluate**  
   `python tools/marketplace_eval/run_eval.py`  
   - Report at `tools/marketplace_eval/reports/marketplace_eval_latest.md` with per-field accuracy and GBP price error/bias.

## Bulk grouping rules
- The mobile app treats each selection session as a flat list, then splits it into balanced drafts using `GROUPING_MAX_PHOTOS_PER_ITEM` (default 8).
- Example outcomes when photos are selected in one batch:
  - 10 photos → 3 drafts sized 4 / 3 / 3
  - 20 photos → 5 drafts sized 4 / 4 / 4 / 4 / 4
  - 30 photos → 8 drafts sized 4 / 4 / 4 / 4 / 4 / 4 / 3 / 3
- Large time gaps between photos (>90s) start a new session. Nothing is dropped; every photo is assigned.
- A small dev log on the Upload screen prints the grouping summary while testing.

## Backend inference
- `app.py` now calls the shared heuristics (`inference_core.infer_listing` + `auto_heuristics_config.json`) for `/process_image` and the multi-photo path.
- Returned draft fields always include GBP price suggestions (`price_low`, `price_mid`, `price_high`) plus title/description/brand/size/colour/condition based on the shared rules.

## Example workflow (small smoke test)
```bash
source .venv/bin/activate || source venv/bin/activate
python tools/selfplay/scrape_vinted_listings.py --max-listings 5
python tools/selfplay/run_selfplay_round.py --max-examples 5
python tools/auto_learn.py
python tools/marketplace_eval/run_eval.py
```

### Bulk upload sanity check
```bash
source .venv/bin/activate || source venv/bin/activate
python app.py  # in one terminal
# In another:
python tools/simulate_bulk_upload.py --count 10 --group-size 4 --base-url http://localhost:5000
```
This prints the drafts created, with GBP suggestions from the shared heuristics.

## Notes
- All prices are treated as GBP (`price_gbp` + `currency: "GBP"`).
- The heuristics stay simple: keyword-based fields + GBP price bands, adjusted by `tools/auto_learn.py`.
- Mobile/backend upload behaviour is untouched; this loop is offline-only.

## User export dataset
- Source file: `data/raw/vinted_export_20251202.zip` (parsed from `listings/index.html` inside the ZIP).
- Regenerate JSONL logs:
  - `source .venv/bin/activate`
  - `python tools/selfplay/run_user_export_eval.py --max-examples 200`
  - `python tools/marketplace_eval/run_eval.py`
- Metrics to watch: brand/size/condition/colour accuracy and GBP price MAE/bias in the "User export summary" section of the latest report.
