import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .infer import BaselineInferencer

FIELDS = ["title", "description", "brand", "size", "colour", "condition", "category"]


@dataclass
class Example:
    example_id: str
    source: str  # "selfplay", "user", or "curated"
    listing_id: Optional[str]
    truth: Dict[str, Any]
    prediction: Dict[str, Any]
    currency: Optional[str] = None


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


def _extract_numeric(value: Any) -> Optional[float]:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_numeric(values: Iterable[Any]) -> Optional[float]:
    for value in values:
        numeric = _extract_numeric(value)
        if numeric is not None:
            return numeric
    return None


def _normalise_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _normalise_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    normalised = {field: _normalise_text(raw.get(field)) for field in FIELDS}
    price_candidate = _first_numeric(
        [
            raw.get("price_gbp"),
            raw.get("price"),
            raw.get("price_mid"),
            raw.get("selected_price"),
            raw.get("price_low"),
            raw.get("price_high"),
        ]
    )
    normalised["price_gbp"] = price_candidate
    return normalised


def _parse_price_range(price_range: Optional[str]) -> Optional[float]:
    if not price_range:
        return None
    numbers = []
    for chunk in str(price_range).replace("£", "").replace("$", "").split("-"):
        try:
            numbers.append(float(chunk.strip()))
        except (TypeError, ValueError):
            continue
    if not numbers:
        return None
    if len(numbers) == 1:
        return numbers[0]
    return sum(numbers) / len(numbers)


def _read_example_file(path: Path, inferencer: BaselineInferencer) -> Example:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Example file {path} must contain a JSON object")

    example_id = str(data.get("id") or path.stem)
    expected_raw = data.get("expected", {})
    truth = {
        "title": _normalise_text(data.get("title") or example_id),
        "description": _normalise_text(data.get("description") or ""),
        "brand": _normalise_text(expected_raw.get("brand")),
        "size": _normalise_text(expected_raw.get("size")),
        "colour": _normalise_text(expected_raw.get("colour")),
        "condition": _normalise_text(expected_raw.get("condition")),
        "category": _normalise_text(expected_raw.get("category")),
        "price_gbp": _parse_price_range(expected_raw.get("price_range")),
    }

    prediction = inferencer.predict(path)
    prediction_map = {
        "title": _normalise_text(example_id),
        "description": _normalise_text(""),
        "brand": _normalise_text(prediction.brand),
        "size": _normalise_text(prediction.size),
        "colour": _normalise_text(prediction.colour),
        "condition": _normalise_text(prediction.condition),
        "category": _normalise_text(prediction.category),
        "price_gbp": prediction.price_gbp,
    }

    return Example(
        example_id=example_id,
        source="curated",
        listing_id=example_id,
        truth=truth,
        prediction=prediction_map,
        currency="GBP",
    )


def load_curated_examples(data_dir: Path, inferencer: BaselineInferencer) -> List[Example]:
    directory = Path(data_dir)
    if not directory.exists():
        return []

    examples: List[Example] = []
    for path in sorted(directory.glob("*.json")):
        try:
            examples.append(_read_example_file(path, inferencer))
        except Exception:
            continue
    return examples


def _extract_id(record: Dict[str, Any]) -> str:
    return str(
        record.get("example_id")
        or record.get("listing_id")
        or record.get("draft_id")
        or record.get("id")
        or "unknown"
    )


def _decode_truth_and_prediction(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    def _from_suffixes() -> Tuple[Dict[str, Any], Dict[str, Any]]:
        truth_map = {}
        pred_map = {}
        for field in FIELDS + ["price_gbp"]:
            truth_val = record.get(f"{field}_truth")
            pred_val = record.get(f"{field}_pred")
            if truth_val is not None:
                truth_map[field] = truth_val
            if pred_val is not None:
                pred_map[field] = pred_val
        if truth_map or pred_map:
            return truth_map, pred_map
        return {}, {}

    if "truth" in record or "prediction" in record:
        return record.get("truth") or {}, record.get("prediction") or {}

    truth = record.get("after") or record.get("correction") or {}
    prediction = record.get("prediction") or record.get("before") or {}
    if truth or prediction:
        return truth, prediction

    return _from_suffixes()


def _records_to_examples(records: List[Dict[str, Any]], source: str) -> List[Example]:
    examples: List[Example] = []
    for record in records:
        truth_raw, pred_raw = _decode_truth_and_prediction(record)
        truth = _normalise_record(truth_raw)
        prediction = _normalise_record(pred_raw)
        examples.append(
            Example(
                example_id=_extract_id(record),
                source=source,
                listing_id=record.get("listing_id"),
                truth=truth,
                prediction=prediction,
                currency=record.get("currency") or "GBP",
            )
        )
    return examples


def _merge_logs(
    predictions: List[Dict[str, Any]], corrections: List[Dict[str, Any]], source: str
) -> List[Example]:
    if corrections:
        return _records_to_examples(corrections, source)
    if predictions:
        return _records_to_examples(predictions, source)
    return []


def load_logged_examples(log_dir: Path, source: str) -> List[Example]:
    log_dir = Path(log_dir)
    predictions_path = log_dir / f"{source}_predictions.jsonl"
    corrections_path = log_dir / f"{source}_corrections.jsonl"

    predictions = _read_jsonl(predictions_path)
    corrections = _read_jsonl(corrections_path)
    return _merge_logs(predictions, corrections, source)


def load_user_export_examples(log_dir: Path) -> List[Example]:
    """Load paired user export predictions/corrections if present."""
    return load_logged_examples(log_dir, "user_export")


def load_all_examples(
    example_dir: Path, logs_dir: Path, inferencer: BaselineInferencer
) -> List[Example]:
    curated = load_curated_examples(example_dir, inferencer)
    selfplay = load_logged_examples(logs_dir, "selfplay")
    user = load_logged_examples(logs_dir, "user")
    user_export = load_user_export_examples(logs_dir)
    return curated + selfplay + user + user_export
