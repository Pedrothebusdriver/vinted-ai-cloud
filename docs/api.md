# FlipLens API quick reference

## POST `/api/infer`

Accepts a single uploaded image (`file`) and returns structured predictions for
clothing attributes. If `OPENAI_API_KEY` is configured, the endpoint will call a
vision-capable OpenAI model (default `gpt-4o-mini`). Without a key it falls back
to the on-device OCR + heuristics pipeline so the Pi stays functional offline.

**Request**

- `file` (multipart image): photo of the clothing item
- Optional query: `fast=1` to skip OCR and run the lightweight heuristic path

**Response**

```json
{
  "brand": "Nike",
  "size": "M",
  "colour": "Black",
  "category": "hoodie",
  "condition": "Good",
  "price_low": 10.5,
  "price_mid": 12.0,
  "price_high": 15.0,
  "label_text": "...",
  "source": "openai"
}
```

`price_*` values are GBP floats when available. Missing fields are `null`.

