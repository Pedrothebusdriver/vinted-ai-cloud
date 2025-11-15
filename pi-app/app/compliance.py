"""Basic image compliance checks used by the Pi pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import cv2

MIN_DIMENSION = int(os.getenv("COMPLIANCE_MIN_DIMENSION", "240"))
MAX_FILE_BYTES = int(os.getenv("COMPLIANCE_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
MAX_FACE_RATIO = float(os.getenv("COMPLIANCE_MAX_FACE_RATIO", "0.45"))

_FACE_DETECTOR = None
_CASCADE_PATH = getattr(cv2.data, "haarcascades", "")
if _CASCADE_PATH:
    cascade_file = Path(_CASCADE_PATH) / "haarcascade_frontalface_default.xml"
    if cascade_file.exists():
        detector = cv2.CascadeClassifier(str(cascade_file))
        if not detector.empty():
            _FACE_DETECTOR = detector


def _percentage(area: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return area / float(total)


def _detect_face_ratio(image) -> float:
    if _FACE_DETECTOR is None:
        return 0.0
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = _FACE_DETECTOR.detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(64, 64),
    )
    if len(faces) == 0:
        return 0.0
    face_area = sum((w * h) for (_, _, w, h) in faces)
    h, w = image.shape[:2]
    return _percentage(face_area, w * h)


def check_image(image_path: Path) -> Tuple[bool, str]:
    """
    Validate an image for downstream listing use.

    Returns:
        (allowed, reason). When ``allowed`` is False the ``reason`` explains
        which rule failed so the caller can log or surface it to the user.
    """
    if not image_path.exists():
        return False, "file missing"
    if image_path.stat().st_size == 0:
        return False, "file empty"
    if image_path.stat().st_size > MAX_FILE_BYTES:
        return False, "file too large"

    img = cv2.imread(str(image_path))
    if img is None:
        return False, "unable to decode"
    height, width = img.shape[:2]
    if min(height, width) < MIN_DIMENSION:
        return False, f"image too small ({width}x{height})"

    face_ratio = _detect_face_ratio(img)
    if face_ratio > MAX_FACE_RATIO:
        pct = round(face_ratio * 100, 1)
        return False, f"face occupies {pct}% of the frame"

    return True, ""


__all__ = ["check_image"]
