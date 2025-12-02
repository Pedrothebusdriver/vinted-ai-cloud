from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .evaluate import EVAL_FIELDS, EvaluationResult, ExampleResult, SourceMetrics


def _format_accuracy(value: float) -> str:
    return f"{value * 100:.1f}%"


def _fmt_price(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"£{value:.2f}"


def _fmt_bias(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value >= 0 else "-"
    return f"{sign}£{abs(value):.2f}"


def _render_field_table(metrics: SourceMetrics) -> List[str]:
    lines = ["| Field | Accuracy | Correct / Total |", "|---|---|---|"]
    for field in EVAL_FIELDS:
        counts = metrics.counts.get(field, {"correct": 0, "total": 0})
        lines.append(
            f"| {field} | {_format_accuracy(metrics.field_accuracies.get(field, 0.0))} | "
            f"{counts['correct']} / {counts['total']} |"
        )
    return lines


def _render_price_summary(metrics: SourceMetrics) -> str:
    return (
        f"Mean abs error: {_fmt_price(metrics.price_mae)}, "
        f"bias: {_fmt_bias(metrics.price_bias)} "
        f"over {metrics.price_count} price pairs"
    )


def _render_summary_block(title: str, metrics: SourceMetrics) -> List[str]:
    lines = [f"## {title}", f"- Examples: {metrics.example_count}", f"- {_render_price_summary(metrics)}"]
    lines.append("")
    lines.append("Field accuracy:")
    lines.extend(_render_field_table(metrics))
    lines.append("")
    return lines


def _pick_price_examples(results: Iterable[ExampleResult], limit: int = 5) -> List[ExampleResult]:
    candidates = [
        res
        for res in results
        if res.price_error is not None and res.truth.get("price_gbp") is not None
    ]
    sorted_candidates = sorted(candidates, key=lambda r: abs(r.price_error or 0), reverse=True)
    return sorted_candidates[:limit]


def _pick_text_misses(results: Iterable[ExampleResult], field: str, limit: int = 5) -> List[ExampleResult]:
    misses = [res for res in results if res.matches.get(field) is False]
    return misses[:limit]


def _render_price_table(examples: List[ExampleResult]) -> List[str]:
    if not examples:
        return ["No price examples available."]
    lines = ["| Example | Title (pred) | Price pred | Price truth | Error |", "|---|---|---|---|---|"]
    for res in examples:
        lines.append(
            f"| {res.example_id} | {res.prediction.get('title') or ''} | "
            f"{_fmt_price(res.prediction.get('price_gbp'))} | "
            f"{_fmt_price(res.truth.get('price_gbp'))} | "
            f"{_fmt_bias(res.price_error)} |"
        )
    return lines


def _render_text_table(examples: List[ExampleResult], field: str) -> List[str]:
    if not examples:
        return [f"No {field} misses found."]
    lines = [f"| Example | {field} truth | {field} pred |", "|---|---|---|"]
    for res in examples:
        lines.append(
            f"| {res.example_id} | {res.truth.get(field) or ''} | {res.prediction.get(field) or ''} |"
        )
    return lines


def _render_source_examples(source: str, results: List[ExampleResult]) -> List[str]:
    lines: List[str] = []
    if not results:
        lines.append(f"No {source} examples available.")
        return lines
    lines.append(f"### {source.title()} examples")
    lines.append("")
    lines.append("Top price misses:")
    lines.extend(_render_price_table(_pick_price_examples(results)))
    lines.append("")
    lines.append("Title misses:")
    lines.extend(_render_text_table(_pick_text_misses(results, "title"), "title"))
    lines.append("")
    lines.append("Description misses:")
    lines.extend(_render_text_table(_pick_text_misses(results, "description"), "description"))
    lines.append("")
    return lines


def build_report_content(evaluation: EvaluationResult) -> str:
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    lines: List[str] = [
        "# Marketplace Evaluation Report",
        f"Generated at: {now}",
        "",
        "## Summary",
        f"- Examples processed: {evaluation.overall.example_count}",
        f"- Price (overall): {_render_price_summary(evaluation.overall)}",
        "- Field accuracy (overall):",
    ]
    lines.extend(_render_field_table(evaluation.overall))
    lines.append("")

    if "selfplay" in evaluation.by_source:
        lines.extend(_render_summary_block("Self-play summary", evaluation.by_source["selfplay"]))
    if "user" in evaluation.by_source:
        lines.extend(_render_summary_block("User corrections summary", evaluation.by_source["user"]))
    if "user_export" in evaluation.by_source:
        lines.extend(_render_summary_block("User export summary", evaluation.by_source["user_export"]))
    if "curated" in evaluation.by_source:
        lines.extend(_render_summary_block("Curated examples", evaluation.by_source["curated"]))

    # Example sections
    by_source_results: Dict[str, List[ExampleResult]] = {}
    for res in evaluation.example_results:
        by_source_results.setdefault(res.source, []).append(res)

    for source, source_results in by_source_results.items():
        lines.extend(_render_source_examples(source, source_results))

    return "\n".join(lines)


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
