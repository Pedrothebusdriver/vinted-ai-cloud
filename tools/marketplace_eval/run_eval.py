import argparse
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
REPO_ROOT = CURRENT_FILE.parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from tools.marketplace_eval.evaluate import evaluate_examples
from tools.marketplace_eval.infer import BaselineInferencer
from tools.marketplace_eval.loader import load_all_examples
from tools.marketplace_eval.report import build_report_content, write_report


def run_eval(data_dir: Path, report_dir: Path, logs_dir: Path) -> Path:
    inferencer = BaselineInferencer()
    examples = load_all_examples(data_dir, logs_dir, inferencer)
    evaluation = evaluate_examples(examples)
    report_content = build_report_content(evaluation)
    report_path = write_report(report_dir, report_content)
    return report_path


def main() -> None:
    default_root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description="Run marketplace evaluation harness.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=default_root / "data" / "marketplace_examples",
        help="Directory containing JSON example files.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=default_root / "reports",
        help="Directory to write evaluation reports.",
    )
    parser.add_argument(
        "--logs-dir",
        type=Path,
        default=default_root / "data",
        help="Directory containing prediction/correction logs (user/selfplay).",
    )
    args = parser.parse_args()

    report_path = run_eval(args.data_dir, args.report_dir, args.logs_dir)
    print(f"Report written to {report_path}")


if __name__ == "__main__":
    main()
