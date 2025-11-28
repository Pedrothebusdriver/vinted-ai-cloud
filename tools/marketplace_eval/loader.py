import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

EXPECTED_FIELDS = ["colour", "category", "brand", "condition", "price_range"]


@dataclass
class Example:
    id: str
    image_path: str
    expected: Dict[str, str]


def _normalise_expected(raw: Dict[str, str]) -> Dict[str, str]:
    """Ensure all expected fields are present and normalised to strings."""
    normalised = {}
    for field in EXPECTED_FIELDS:
        value = raw.get(field, "") if isinstance(raw, dict) else ""
        normalised[field] = str(value).strip()
    return normalised


def _read_example_file(path: Path) -> Example:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, dict):
        raise ValueError(f"Example file {path} must contain a JSON object")

    example_id = str(data.get("id") or path.stem)
    image_path = str(data.get("image_path") or "")
    expected_raw = data.get("expected", {})
    expected = _normalise_expected(expected_raw)

    return Example(id=example_id, image_path=image_path, expected=expected)


def load_examples(data_dir: Path) -> List[Example]:
    """Load all JSON example files from the data directory."""
    directory = Path(data_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Example directory not found: {directory}")

    examples: List[Example] = []
    for path in sorted(directory.glob("*.json")):
        examples.append(_read_example_file(path))

    if not examples:
        raise ValueError(f"No examples found in {directory}")

    return examples
