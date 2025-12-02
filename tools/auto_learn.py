"""
Consume correction logs (user + self-play) and adjust the heuristic config in GBP.

CLI:
    python tools/auto_learn.py
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

CONFIG_PATH = Path("auto_heuristics_config.json")
LOGS_DIR = Path("tools/marketplace_eval/data")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _normalise_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_numeric(values: List[Any]) -> Optional[float]:
    for value in values:
        try:
            if value is None or isinstance(value, bool):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _decode_truth_pred(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    if "truth" in record or "prediction" in record:
        return record.get("truth") or {}, record.get("prediction") or {}
    truth = record.get("after") or record.get("correction") or {}
    prediction = record.get("prediction") or record.get("before") or {}
    return truth or {}, prediction or {}


def _extract_price(record: Dict[str, Any]) -> Optional[float]:
    return _first_numeric(
        [
            record.get("price_gbp"),
            record.get("selected_price"),
            record.get("price_mid"),
            record.get("price"),
            record.get("price_low"),
            record.get("price_high"),
        ]
    )


@dataclass
class PriceStats:
    errors: List[float]

    def add(self, truth: Optional[float], pred: Optional[float]) -> None:
        if truth is None or pred is None:
            return
        self.errors.append(pred - truth)

    @property
    def bias(self) -> Optional[float]:
        if not self.errors:
            return None
        return mean(self.errors)

    @property
    def mae(self) -> Optional[float]:
        if not self.errors:
            return None
        return mean(abs(err) for err in self.errors)

    @property
    def count(self) -> int:
        return len(self.errors)


def _load_corrections(logs_dir: Path, source: str) -> List[Dict[str, Any]]:
    corrections_path = logs_dir / f"{source}_corrections.jsonl"
    predictions_path = logs_dir / f"{source}_predictions.jsonl"
    corrections = _read_jsonl(corrections_path)
    return corrections if corrections else _read_jsonl(predictions_path)


def _collect_price_biases(
    logs_dir: Path,
) -> Tuple[Dict[str, PriceStats], Dict[str, PriceStats], Dict[str, PriceStats], Dict[str, int]]:
    brand_bias: Dict[str, PriceStats] = defaultdict(lambda: PriceStats(errors=[]))
    category_bias: Dict[str, PriceStats] = defaultdict(lambda: PriceStats(errors=[]))
    condition_bias: Dict[str, PriceStats] = defaultdict(lambda: PriceStats(errors=[]))
    counts: Dict[str, int] = {"user": 0, "selfplay": 0, "user_export": 0}

    for source in ("user", "selfplay", "user_export"):
        records = _load_corrections(logs_dir, source)
        counts[source] = len(records)
        for record in records:
            truth_raw, pred_raw = _decode_truth_pred(record)
            truth_price = _extract_price(truth_raw)
            pred_price = _extract_price(pred_raw)
            brand = _normalise_text(truth_raw.get("brand"))
            category = _normalise_text(truth_raw.get("category"))
            condition = _normalise_text(truth_raw.get("condition"))
            if brand:
                brand_bias[brand].add(truth_price, pred_price)
            if category:
                category_bias[category].add(truth_price, pred_price)
            if condition:
                condition_bias[condition].add(truth_price, pred_price)
    return brand_bias, category_bias, condition_bias, counts


def _adjust_range(price_range: Dict[str, Any], bias: float) -> Dict[str, float]:
    current_min = float(price_range.get("min", 1.0))
    current_max = float(price_range.get("max", max(current_min + 1.0, 5.0)))
    new_min = max(1.0, round(current_min + bias, 2))
    new_max = max(new_min + 0.5, round(current_max + bias, 2))
    return {"min": new_min, "max": new_max}


def _apply_price_updates(
    config: Dict[str, Any],
    biases: Dict[str, PriceStats],
    target_key: str,
    min_examples: int = 2,
) -> List[str]:
    updates: List[str] = []
    base_range = config.get("base_price_gbp", {"min": 8.0, "max": 45.0})
    table: Dict[str, Dict[str, float]] = config.setdefault(target_key, {})
    for label, stats in biases.items():
        if stats.count < min_examples or stats.bias is None:
            continue
        adjusted = _adjust_range(table.get(label, base_range), stats.bias)
        table[label] = adjusted
        updates.append(f"{label}: bias {stats.bias:+.2f} -> range £{adjusted['min']:.2f}-£{adjusted['max']:.2f}")
    return updates


def _apply_condition_updates(
    config: Dict[str, Any],
    condition_bias: Dict[str, PriceStats],
    base_mid: float,
    min_examples: int = 3,
) -> List[str]:
    updates: List[str] = []
    multipliers = config.setdefault("condition_multipliers", {})
    for condition, stats in condition_bias.items():
        if stats.count < min_examples or stats.bias is None:
            continue
        current = float(multipliers.get(condition, 1.0))
        delta = stats.bias / max(base_mid, 1.0)
        adjusted = round(max(0.5, min(1.6, current + (delta * 0.3))), 2)
        multipliers[condition] = adjusted
        updates.append(f"{condition}: bias {stats.bias:+.2f} -> multiplier {adjusted}")
    return updates


def _load_config(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _write_config(path: Path, config: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(config, handle, indent=2, sort_keys=True)
        handle.write("\n")


def main() -> None:
    config = _load_config(CONFIG_PATH)
    brand_bias, category_bias, condition_bias, counts = _collect_price_biases(LOGS_DIR)

    base_range = config.get("base_price_gbp", {"min": 8.0, "max": 45.0})
    base_mid = (float(base_range.get("min", 8.0)) + float(base_range.get("max", 45.0))) / 2.0

    updates: List[str] = []
    updates.extend(_apply_price_updates(config, brand_bias, "brand_price_overrides"))
    updates.extend(_apply_price_updates(config, category_bias, "category_price_overrides"))
    updates.extend(_apply_condition_updates(config, condition_bias, base_mid))

    _write_config(CONFIG_PATH, config)

    print(
        "Ingested corrections - "
        f"user: {counts['user']}, selfplay: {counts['selfplay']}, user_export: {counts['user_export']}"
    )
    if updates:
        print("Applied updates:")
        for line in updates:
            print(f"- {line}")
    else:
        print("No price/condition updates applied (insufficient signal).")
    print(f"Config written to {CONFIG_PATH}")


if __name__ == "__main__":
    main()
