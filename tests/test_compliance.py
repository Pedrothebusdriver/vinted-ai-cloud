from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

# Make sure we import from the Pi app package (pi-app/app),
# NOT the top-level app.py in the repo.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pi-app"))

from app import compliance  # noqa: E402


def _write_image(tmp_path: Path, name: str, data: np.ndarray) -> Path:
    path = tmp_path / name
    cv2.imwrite(str(path), data)
    return path


def test_check_image_rejects_small_photo(tmp_path):
    img = np.full((100, 100, 3), 128, dtype=np.uint8)
    path = _write_image(tmp_path, "small.jpg", img)
    allowed, reason = compliance.check_image(path)
    assert not allowed
    assert "too small" in reason


def test_check_image_rejects_blurry_photo(tmp_path):
    img = np.full((512, 512, 3), 90, dtype=np.uint8)
    path = _write_image(tmp_path, "flat.jpg", img)
    allowed, reason = compliance.check_image(path)
    assert not allowed
    assert "blurry" in reason


def test_check_image_accepts_valid_gradient(tmp_path):
    gradient = np.linspace(0, 255, 512, dtype=np.uint8)
    img = np.stack([np.tile(gradient, (512, 1))] * 3, axis=-1)
    path = _write_image(tmp_path, "ok.jpg", img)
    allowed, reason = compliance.check_image(path)
    assert allowed, reason


def test_check_image_handles_grayscale(tmp_path):
    gradient = np.tile(np.linspace(0, 255, 512, dtype=np.uint8), (512, 1))
    path = _write_image(tmp_path, "gray.jpg", gradient)
    allowed, reason = compliance.check_image(path)
    assert allowed, reason


def test_detect_body_ratio_handles_scalar_weights(monkeypatch, tmp_path):
    class StubHog:
        def detectMultiScale(self, image, **kwargs):
            # Returns a single rect with scalar weight to mimic OpenCV variations.
            return [(0, 0, 50, 100)], np.array(0.5)

    monkeypatch.setattr(compliance, "_HOG", StubHog())
    gradient = np.linspace(0, 255, 512, dtype=np.uint8)
    img = np.stack([np.tile(gradient, (512, 1))] * 3, axis=-1)
    path = _write_image(tmp_path, "stub.jpg", img)
    allowed, reason = compliance.check_image(path)
    assert allowed, reason


def test_detect_body_ratio_handles_detector_errors(monkeypatch, tmp_path):
    class StubHog:
        def detectMultiScale(self, image, **kwargs):
            raise ValueError("oops")

    monkeypatch.setattr(compliance, "_HOG", StubHog())
    gradient = np.linspace(0, 255, 512, dtype=np.uint8)
    img = np.stack([np.tile(gradient, (512, 1))] * 3, axis=-1)
    path = _write_image(tmp_path, "error.jpg", img)
    allowed, reason = compliance.check_image(path)
    assert allowed, reason
