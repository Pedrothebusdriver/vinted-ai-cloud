from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.ingest import (  # type: ignore  # noqa: E402
    ProcessedPhoto,
    _detect_colour_from_photos,
    _normalize_metadata,
)


def test_detect_colour_returns_detector_value(tmp_path):
    photo_path = tmp_path / "sample.jpg"
    photo_path.write_bytes(b"fake")
    photo = ProcessedPhoto(original=photo_path, optimised=photo_path)

    def fake_detector(path: Path) -> str:
        assert path == photo_path
        return "#ff00ff"

    assert _detect_colour_from_photos(fake_detector, [photo]) == "#ff00ff"


def test_detect_colour_handles_missing_photos():
    assert _detect_colour_from_photos(lambda _: "blue", []) == "Unknown"


def test_normalize_metadata_lowercases_and_trims():
    metadata = {
        "Brand": "  Nike ",
        "SIZE": " M ",
        "Custom": "value",
        "vinted": {"Title": "  Hoodie "},
    }
    cleaned = _normalize_metadata(metadata)
    assert cleaned["brand"] == "Nike"
    assert cleaned["size"] == "M"
    assert cleaned["Custom"] == "value"
    assert cleaned["vinted"]["title"] == "Hoodie"
