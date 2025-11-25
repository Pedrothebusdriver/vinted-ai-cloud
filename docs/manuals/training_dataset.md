# FlipLens training dataset (local)

Store legal, non-scraped clothing photos under `data/training-images/` and
describe them in `data/training_items.jsonl` (one JSON object per line).

## `data/training_items.jsonl` format

Each line should include the image path (relative to repo root) and labels:

```json
{
  "image_path": "data/training-images/hoodies/red_hoodie.jpg",
  "brand": "Nike",
  "size": "M",
  "colour": "Red",
  "category": "hoodie",
  "condition": "Good",
  "price_low": 12.0,
  "price_mid": 15.0,
  "price_high": 18.0
}
```

- `image_path` must point to a local file Pete controls.
- Prices are optional but help the eval loop score pricing accuracy.
- Add as many rows as you like; the manifest/tooling will pick them all up.

## Folder layout

```
 data/
 ├─ training-images/        # your photos go here (any nested folders ok)
 ├─ training_items.jsonl    # labels per image
```

Drop new photos + labels, rerun `tools/build_eval_manifest.py`, and the sampler
+ eval workflows will automatically target your dataset.
