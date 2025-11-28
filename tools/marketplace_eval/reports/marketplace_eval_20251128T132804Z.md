# Marketplace Evaluation Report
Generated at: 2025-11-28T13:28:04Z

## Summary
- Overall accuracy: 70.0%
- Field accuracy:

| Field | Accuracy | Correct / Total |
|---|---|---|
| colour | 100.0% | 2 / 2 |
| category | 100.0% | 2 / 2 |
| brand | 50.0% | 1 / 2 |
| condition | 50.0% | 1 / 2 |
| price_range | 50.0% | 1 / 2 |

## Examples
| Example | Colour | Category | Brand | Condition | Price Range |
|---|---|---|---|---|---|
|green_canvas_tote_bag|✅ exp: Green / pred: Green|✅ exp: Bag / pred: Bag|⚠️ exp: Everlane / pred: unknown|⚠️ exp: Gently used / pred: Used - good|⚠️ exp: $40-$60 / pred: unknown|
|red_vintage_leather_jacket|✅ exp: Red / pred: Red|✅ exp: Jacket / pred: Jacket|✅ exp: Levi's / pred: Levi's|✅ exp: Vintage / pred: Vintage|✅ exp: $70-$90 / pred: $70-$90|