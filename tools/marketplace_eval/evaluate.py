from dataclasses import dataclass
from typing import Dict, List

from .loader import EXPECTED_FIELDS, Example
from .infer import Prediction


def _normalise(value: str) -> str:
    return (value or "").strip().lower()


@dataclass
class ExampleResult:
    example_id: str
    expected: Dict[str, str]
    predicted: Dict[str, str]
    matches: Dict[str, bool]


@dataclass
class Metrics:
    overall_accuracy: float
    field_accuracies: Dict[str, float]
    counts: Dict[str, Dict[str, int]]


@dataclass
class EvaluationResult:
    metrics: Metrics
    example_results: List[ExampleResult]


def evaluate_predictions(
    examples: List[Example], predictions: List[Prediction]
) -> EvaluationResult:
    if len(examples) != len(predictions):
        raise ValueError("Examples and predictions must have the same length")

    field_correct: Dict[str, int] = {field: 0 for field in EXPECTED_FIELDS}
    example_results: List[ExampleResult] = []

    for example, prediction in zip(examples, predictions):
        predicted_map = {
            "colour": prediction.colour,
            "category": prediction.category,
            "brand": prediction.brand,
            "condition": prediction.condition,
            "price_range": prediction.price_range,
        }
        matches = {
            field: _normalise(predicted_map[field]) == _normalise(example.expected[field])
            for field in EXPECTED_FIELDS
        }
        for field, match in matches.items():
            field_correct[field] += 1 if match else 0

        example_results.append(
            ExampleResult(
                example_id=example.id,
                expected=example.expected,
                predicted=predicted_map,
                matches=matches,
            )
        )

    total = len(examples)
    field_accuracies = {
        field: (field_correct[field] / total) if total else 0.0 for field in EXPECTED_FIELDS
    }
    total_fields = total * len(EXPECTED_FIELDS) if total else 1
    overall_accuracy = sum(field_correct.values()) / total_fields

    metrics = Metrics(
        overall_accuracy=overall_accuracy,
        field_accuracies=field_accuracies,
        counts={field: {"correct": field_correct[field], "total": total} for field in EXPECTED_FIELDS},
    )

    return EvaluationResult(metrics=metrics, example_results=example_results)
