#!/usr/bin/env python3
"""
Quick helper to inspect learning logs.

Prints counts for predictions/corrections and shows the last few corrections.
"""
import json
from pathlib import Path

DATA_DIR = Path("tools/marketplace_eval/data")
CORRECTIONS = DATA_DIR / "user_corrections.jsonl"
PREDICTIONS = DATA_DIR / "user_predictions.jsonl"


def count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def tail(path: Path, n: int = 3):
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return lines[-n:]


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    predictions = count_lines(PREDICTIONS)
    corrections = count_lines(CORRECTIONS)

    print(f"Predictions logged: {predictions} ({PREDICTIONS})")
    print(f"User corrections logged: {corrections} ({CORRECTIONS})")

    if predictions:
        print("Last predictions:")
        for line in tail(PREDICTIONS, 3):
            try:
                obj = json.loads(line)
                print(f"- draft_id={obj.get('draft_id')} ts={obj.get('timestamp')}")
            except Exception:
                print(f"- {line}")

    if corrections:
        print("Last corrections:")
        for line in tail(CORRECTIONS, 3):
            try:
                obj = json.loads(line)
                print(f"- draft_id={obj.get('draft_id')} ts={obj.get('timestamp')}")
            except Exception:
                print(f"- {line}")

    if predictions and corrections:
        print("Recent prediction/correction pairs:")
        preds = tail(PREDICTIONS, 3)
        corrs = tail(CORRECTIONS, 3)
        for p_line, c_line in zip(preds, corrs):
            try:
                p = json.loads(p_line)
                c = json.loads(c_line)
                print(
                    f"- draft {p.get('draft_id')} pred_ts={p.get('timestamp')} correction_ts={c.get('timestamp')}"
                )
            except Exception:
                print(f"- pred={p_line} correction={c_line}")


if __name__ == "__main__":
    main()
