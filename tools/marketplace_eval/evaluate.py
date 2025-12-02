from dataclasses import dataclass
from difflib import SequenceMatcher
from statistics import mean
from typing import Any, Dict, List, Optional

from .loader import Example

EVAL_FIELDS = ["title", "description", "brand", "size", "colour", "condition"]


def _normalise(value: Any) -> str:
    return str(value or "").strip().lower()


def _token_set(text: str) -> set:
    return {token for token in _normalise(text).split() if len(token) > 2}


def _fuzzy_match_text(truth: Optional[str], pred: Optional[str]) -> Optional[bool]:
    if not truth:
        return None
    if not pred:
        return False
    ratio = SequenceMatcher(None, _normalise(truth), _normalise(pred)).ratio()
    return ratio >= 0.6


def _coverage_match(truth: Optional[str], pred: Optional[str]) -> Optional[bool]:
    if not truth:
        return None
    if not pred:
        return False
    truth_tokens = _token_set(truth)
    pred_tokens = _token_set(pred)
    return bool(truth_tokens and pred_tokens and truth_tokens.intersection(pred_tokens))


def _exact_match(truth: Optional[str], pred: Optional[str]) -> Optional[bool]:
    if truth is None:
        return None
    return _normalise(truth) == _normalise(pred)


def _price_error(truth: Any, pred: Any) -> Optional[float]:
    try:
        if truth is None or pred is None:
            return None
        return float(pred) - float(truth)
    except (TypeError, ValueError):
        return None


@dataclass
class ExampleResult:
    example_id: str
    source: str
    listing_id: Optional[str]
    matches: Dict[str, Optional[bool]]
    price_error: Optional[float]
    truth: Dict[str, Any]
    prediction: Dict[str, Any]


@dataclass
class SourceMetrics:
    field_accuracies: Dict[str, float]
    counts: Dict[str, Dict[str, int]]
    price_mae: Optional[float]
    price_bias: Optional[float]
    price_count: int
    example_count: int


@dataclass
class EvaluationResult:
    overall: SourceMetrics
    by_source: Dict[str, SourceMetrics]
    example_results: List[ExampleResult]


def _score_examples(examples: List[Example]) -> List[ExampleResult]:
    results: List[ExampleResult] = []
    for example in examples:
        truth = example.truth
        pred = example.prediction
        matches: Dict[str, Optional[bool]] = {
            "title": _fuzzy_match_text(truth.get("title"), pred.get("title")),
            "description": _coverage_match(truth.get("description"), pred.get("description")),
            "brand": _exact_match(truth.get("brand"), pred.get("brand")),
            "size": _exact_match(truth.get("size"), pred.get("size")),
            "colour": _exact_match(truth.get("colour"), pred.get("colour")),
            "condition": _exact_match(truth.get("condition"), pred.get("condition")),
        }
        price_err = _price_error(truth.get("price_gbp"), pred.get("price_gbp"))
        results.append(
            ExampleResult(
                example_id=example.example_id,
                source=example.source,
                listing_id=example.listing_id,
                matches=matches,
                price_error=price_err,
                truth=truth,
                prediction=pred,
            )
        )
    return results


def _compute_metrics(results: List[ExampleResult]) -> SourceMetrics:
    counts = {field: {"correct": 0, "total": 0} for field in EVAL_FIELDS}
    price_errors: List[float] = []
    for result in results:
        for field in EVAL_FIELDS:
            match = result.matches.get(field)
            truth_has_value = bool(_normalise(result.truth.get(field)))
            if match is None or not truth_has_value:
                continue
            counts[field]["total"] += 1
            if match:
                counts[field]["correct"] += 1

        if result.price_error is not None and result.truth.get("price_gbp") is not None:
            price_errors.append(result.price_error)

    field_accuracies = {}
    for field, payload in counts.items():
        total = payload["total"]
        acc = (payload["correct"] / total) if total else 0.0
        field_accuracies[field] = acc

    price_mae = mean(abs(err) for err in price_errors) if price_errors else None
    price_bias = mean(price_errors) if price_errors else None

    return SourceMetrics(
        field_accuracies=field_accuracies,
        counts=counts,
        price_mae=price_mae,
        price_bias=price_bias,
        price_count=len(price_errors),
        example_count=len(results),
    )


def evaluate_examples(examples: List[Example]) -> EvaluationResult:
    example_results = _score_examples(examples)
    by_source: Dict[str, List[ExampleResult]] = {}
    for result in example_results:
        by_source.setdefault(result.source, []).append(result)

    source_metrics: Dict[str, SourceMetrics] = {
        source: _compute_metrics(res_list) for source, res_list in by_source.items()
    }
    overall = _compute_metrics(example_results)

    return EvaluationResult(
        overall=overall,
        by_source=source_metrics,
        example_results=example_results,
    )
