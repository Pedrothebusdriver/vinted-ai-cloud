"""Evaluate /api/infer against local training labels and post summary."""

import json
import mimetypes
import os
import pathlib
from datetime import datetime
from typing import Dict, Iterable, Tuple

import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST_DIR = ROOT / ".agent" / "sampler"
DEFAULT_DATA_OUT = ROOT / "data" / "evals"

WEBHOOK_EVAL = os.environ.get("DISCORD_WEBHOOK_AI_TEST", os.environ.get("DISCORD_AGENT_WEBHOOK", "")).strip()
SUMMARY_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_GENERAL", os.environ.get("DISCORD_WEBHOOK_URL", "")).strip()
INFER_URL = os.environ.get("PI_INFER_URL", "http://127.0.0.1:8080/api/infer").strip()
MAX_POSTS = int(os.environ.get("EVAL_MAX_DISCORD_POSTS", "5"))


def pick_manifest() -> pathlib.Path:
    env_path = os.environ.get("EVAL_MANIFEST")
    if env_path:
        return pathlib.Path(env_path)
    manifests = sorted(DEFAULT_MANIFEST_DIR.glob("manifest-*.json"), reverse=True)
    if not manifests:
        raise SystemExit("No manifest files available under .agent/sampler")
    return manifests[0]


def load_manifest(path: pathlib.Path) -> Dict:
    data = json.loads(path.read_text())
    if not data.get("items"):
        raise SystemExit(f"Manifest has no items: {path}")
    return data


def infer_one(img_path: pathlib.Path) -> Dict:
    with open(img_path, "rb") as f:
        r = requests.post(
            INFER_URL,
            files={"file": (img_path.name, f, mimetypes.guess_type(img_path.name)[0] or "application/octet-stream")},
            timeout=45,
        )
    r.raise_for_status()
    return r.json()


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _price(val) -> float:
    try:
        return float(val)
    except Exception:
        return float("nan")


def compare(pred: Dict, truth: Dict) -> Tuple[Dict[str, bool], float]:
    fields = {f: _norm(pred.get(f, "")) == _norm(truth.get(f, "")) for f in ["brand", "size", "colour", "category", "condition"]}
    p_pred = _price(pred.get("price_mid"))
    p_true = _price(truth.get("price_mid"))
    price_error = abs(p_pred - p_true) if not any(map(lambda x: x != x, [p_pred, p_true])) else float("nan")
    return fields, price_error


def post_to_discord(content: str, hook: str):
    if not hook:
        return
    try:
        requests.post(hook, json={"content": content}, timeout=20)
    except Exception:
        pass


def main():
    manifest_path = pick_manifest()
    manifest = load_manifest(manifest_path)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    results_dir = DEFAULT_DATA_OUT / datetime.utcnow().strftime("%Y-%m-%d")
    results_dir.mkdir(parents=True, exist_ok=True)
    results_path = results_dir / "eval-results.jsonl"

    field_hits = {"brand": 0, "size": 0, "colour": 0, "category": 0, "condition": 0}
    price_errors = []
    lines = []
    posted = 0

    for item in manifest["items"]:
        img_path = pathlib.Path(item["image_path"])
        if not img_path.is_absolute():
            img_path = ROOT / img_path
        truth = item.get("labels", {})
        try:
            pred = infer_one(img_path)
            fields, price_err = compare(pred, truth)
            for k, ok in fields.items():
                field_hits[k] += int(ok)
            if price_err == price_err:  # not NaN
                price_errors.append(price_err)
            line = {
                "id": item.get("id"),
                "file": str(img_path.relative_to(ROOT)),
                "pred": pred,
                "truth": truth,
                "fields": fields,
                "price_error": None if price_err != price_err else price_err,
                "ts": datetime.utcnow().isoformat() + "Z",
            }
            lines.append(line)

            if posted < MAX_POSTS and WEBHOOK_EVAL:
                summary = ", ".join([f"{k}:{'✅' if v else '❌'}" for k, v in fields.items()])
                post_to_discord(f"Eval `{img_path.name}` — {summary}", WEBHOOK_EVAL)
                posted += 1
        except Exception as exc:
            lines.append({"file": str(img_path), "error": str(exc), "ts": datetime.utcnow().isoformat() + "Z"})

    with open(results_path, "a", encoding="utf-8") as f:
        for obj in lines:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")

    total = len(manifest["items"])
    summary = {
        "ts": ts,
        "manifest": str(manifest_path),
        "total": total,
        "field_hits": field_hits,
        "price_mae": (sum(price_errors) / len(price_errors)) if price_errors else None,
    }

    out_summary = DEFAULT_MANIFEST_DIR / f"summary-{ts}.json"
    out_summary.write_text(json.dumps(summary, indent=2))

    pct = {k: (field_hits[k] / total * 100.0) if total else 0 for k in field_hits}
    summary_text = (
        f"Eval {total} items from `{manifest_path.name}`\n"
        f"brand {pct['brand']:.0f}% | size {pct['size']:.0f}% | colour {pct['colour']:.0f}% | category {pct['category']:.0f}%"
    )
    post_to_discord(summary_text, SUMMARY_WEBHOOK)
    print(summary_text)


if __name__ == "__main__":
    main()
