from datetime import datetime
from pathlib import Path
from typing import List

from .evaluate import EvaluationResult, ExampleResult


def _format_accuracy(value: float) -> str:
    return f"{value * 100:.1f}%"


def _render_example_row(result: ExampleResult) -> str:
    cells = [
        result.example_id,
        _format_expected_vs_predicted("colour", result),
        _format_expected_vs_predicted("category", result),
        _format_expected_vs_predicted("brand", result),
        _format_expected_vs_predicted("condition", result),
        _format_expected_vs_predicted("price_range", result),
    ]
    return "|" + "|".join(cells) + "|"


def _format_expected_vs_predicted(field: str, result: ExampleResult) -> str:
    expected = result.expected.get(field, "")
    predicted = result.predicted.get(field, "")
    status = "✅" if result.matches.get(field) else "⚠️"
    return f"{status} exp: {expected} / pred: {predicted}"


def build_report_content(evaluation: EvaluationResult) -> str:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    summary_lines = [
        "# Marketplace Evaluation Report",
        f"Generated at: {now}",
        "",
        "## Summary",
        f"- Overall accuracy: {_format_accuracy(evaluation.metrics.overall_accuracy)}",
    ]

    summary_lines.append("- Field accuracy:")
    summary_lines.append("")
    summary_lines.append("| Field | Accuracy | Correct / Total |")
    summary_lines.append("|---|---|---|")
    for field, accuracy in evaluation.metrics.field_accuracies.items():
        counts = evaluation.metrics.counts[field]
        summary_lines.append(
            f"| {field} | {_format_accuracy(accuracy)} | {counts['correct']} / {counts['total']} |"
        )

    summary_lines.append("")
    summary_lines.append("## Examples")
    summary_lines.append(
        "| Example | Colour | Category | Brand | Condition | Price Range |"
    )
    summary_lines.append("|---|---|---|---|---|---|")
    for example_result in evaluation.example_results:
        summary_lines.append(_render_example_row(example_result))

    return "\n".join(summary_lines)


def write_report(report_dir: Path, content: str) -> Path:
    """Write the latest report and a timestamped copy."""
    report_dir.mkdir(parents=True, exist_ok=True)
    latest_path = report_dir / "marketplace_eval_latest.md"
    with latest_path.open("w", encoding="utf-8") as handle:
        handle.write(content)

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    dated_path = report_dir / f"marketplace_eval_{timestamp}.md"
    with dated_path.open("w", encoding="utf-8") as handle:
        handle.write(content)

    return latest_path
