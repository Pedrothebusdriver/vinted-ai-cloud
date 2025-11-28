# Marketplace Evaluation Harness

The marketplace evaluation harness lives under `tools/marketplace_eval`. It ships with a lightweight, filename-based baseline so it can run without model dependencies while staying easy to extend when a real vision model is available.

## Add new examples
Examples are JSON files under `tools/marketplace_eval/data/marketplace_examples`. Add a new file per example with the following shape:

```json
{
  "id": "descriptive_identifier",
  "image_path": "images/path_to_image_file.jpg",
  "expected": {
    "colour": "Red",
    "category": "Jacket",
    "brand": "Brand name",
    "condition": "New with tags",
    "price_range": "$70-$90"
  }
}
```

Notes:
- `image_path` can point to a future image; the baseline inferencer only inspects the filename tokens.
- Keep all five expected fields populated so accuracy stays consistent.
- Current placeholder examples: `red_vintage_leather_jacket` and `green_canvas_tote_bag` (images to be added later).

## Run the evaluation
From the repository root:

```
python tools/marketplace_eval/run_eval.py
```

Optional flags:
- `--data-dir` to point at a different example directory.
- `--report-dir` to change where markdown reports are written.

## Reports
Reports are written to `tools/marketplace_eval/reports/marketplace_eval_latest.md` and a timestamped copy in the same directory (e.g., `tools/marketplace_eval/reports/marketplace_eval_20251128T132804Z.md`).

The latest run (baseline heuristics) achieved 70.0% overall accuracy across 2 examples. See the latest report for field-level detail and per-example breakdowns.

## Current weaknesses
- Brand coverage is limited (50% accuracy); niche labels like Everlane are returned as `unknown`.
- Condition grading is coarse (50% accuracy); subtle states such as "Gently used" collapse into broader buckets.
- Price range inference depends on numeric hints in filenames and falls back to `unknown`, leaving 50% of current cases uncovered.
- Only two placeholder examples exist and no images are loaded yet, so results may not reflect real-world variability.
