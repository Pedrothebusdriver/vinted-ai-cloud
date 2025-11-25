"""Image compliance checks for uploads.

Validates uploaded images for size, blur, edge energy, and dominant faces or
bodies. Configuration is driven by environment variables and uses OpenCV
primitives when available.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

import cv2

MIN_DIMENSION = int(os.getenv("COMPLIANCE_MIN_DIMENSION", "240"))
MAX_FILE_BYTES = int(os.getenv("COMPLIANCE_MAX_FILE_BYTES", str(15 * 1024 * 1024)))
MAX_FACE_RATIO = float(os.getenv("COMPLIANCE_MAX_FACE_RATIO", "0.45"))
MAX_BODY_RATIO = float(os.getenv("COMPLIANCE_MAX_BODY_RATIO", "0.35"))
BLUR_THRESHOLD = float(os.getenv("COMPLIANCE_MIN_LAPLACE", "35"))
EDGE_ENERGY_THRESHOLD = float(os.getenv("COMPLIANCE_MIN_EDGE_ENERGY", "1.5"))
BODY_CONFIDENCE = float(os.getenv("COMPLIANCE_BODY_CONFIDENCE", "0.3"))


_CASCADE_PATH = getattr(cv2.data, "haarcascades", "")
_FACE_DETECTOR = None
if _CASCADE_PATH:
    cascade_file = Path(_CASCADE_PATH) / "haarcascade_frontalface_default.xml"
    if cascade_file.exists():
        face_detector = cv2.CascadeClassifier(str(cascade_file))
        if not face_detector.empty():
            _FACE_DETECTOR = face_detector

_HOG = cv2.HOGDescriptor()
try:
    _HOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
except Exception:  # pragma: no cover - OpenCV guard
    _HOG = None


def _percentage(area: int, total: int) -> float:
    """Return ``area`` as a percentage of ``total``."""
    if total <= 0:
        return 0.0
    return area / float(total)


def _detect_face_ratio(image) -> float:
    """Return the fraction of the image covered by detected faces."""
    if _FACE_DETECTOR is None:
        return 0.0

    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = _FACE_DETECTOR.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(64, 64)
        )
    except Exception:
        return 0.0

    if len(faces) == 0:
        return 0.0

    face_area = sum((w * h) for (_, _, w, h) in faces)
    h, w = image.shape[:2]
    return _percentage(face_area, w * h)


def _flatten_weights(weights):
    """Best-effort flattening of HOG weights to a sequence or scalar.

    OpenCV can return weights as scalars, 1D arrays, 2D arrays, or lists.
    This helper keeps the value usable without raising IndexError.
    """

    if weights is None:
        return None
    try:
        return weights.ravel()
    except Exception:
        pass
    try:
        return list(weights)
    except Exception:
        return weights


def _weight_for_index(weights_flat, idx: int) -> float:
    """Retrieve a weight value for the given index with safe fallbacks."""

    if weights_flat is None:
        return 1.0

    try:
        length = len(weights_flat)  # type: ignore[arg-type]
    except Exception:
        length = None

    if length is None:
        try:
            return float(weights_flat)
        except Exception:
            return 1.0

    if idx < length:
        try:
            return float(weights_flat[idx])
        except Exception:
            return 1.0

    return 1.0


def _detect_body_ratio(image) -> float:
    """Return the fraction of the image covered by the largest detected body."""
    if _HOG is None:
        return 0.0

    height, width = image.shape[:2]
    total = width * height
    try:
        rects, weights = _HOG.detectMultiScale(
            image, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
    except Exception:  # pragma: no cover - GPU/OpenCV guard
        return 0.0

    weights_flat = _flatten_weights(weights)

    ratios = []
    for idx, (_, _, w, h) in enumerate(rects):
        weight = _weight_for_index(weights_flat, idx)
        if weight < BODY_CONFIDENCE:
            continue
        ratios.append(_percentage(w * h, total))

    return max(ratios, default=0.0)


def _variance_of_laplacian(image) -> float:
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return cv2.Laplacian(gray, cv2.CV_64F).var()
    except Exception:
        return 0.0


def _edge_energy(image) -> float:
    """Measure first-order edge energy via Sobel gradients."""
    try:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        grad_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        magnitude = cv2.magnitude(grad_x, grad_y)
        return float(magnitude.mean())
    except Exception:
        return 0.0


def _is_blurry(image) -> bool:
    try:
        laplace_variance = _variance_of_laplacian(image)
        if laplace_variance >= BLUR_THRESHOLD:
            return False
        edge_energy = _edge_energy(image)
        return edge_energy < EDGE_ENERGY_THRESHOLD
    except Exception:
        return True


def check_image(image_path: Path) -> Tuple[bool, str]:
    """Validate an image for downstream listing use.

    Returns:
        (allowed, reason). When ``allowed`` is False the ``reason`` explains
        which rule failed so the caller can log or surface it to the user.
    """
    if not image_path.exists():
        return False, "file missing"

    try:
        stat = image_path.stat()
    except OSError:
        return False, "file missing"

    if stat.st_size == 0:
        return False, "file empty"
    if stat.st_size > MAX_FILE_BYTES:
        return False, "file too large"

    img = cv2.imread(str(image_path))
    if img is None:
        return False, "unable to decode"

    # Normalise to BGR for downstream detectors and guards.
    try:
        if len(img.shape) == 2 or (len(img.shape) == 3 and img.shape[2] == 1):
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    except Exception:
        return False, "unable to decode"

    height, width = img.shape[:2]
    if min(height, width) < MIN_DIMENSION:
        return False, f"image too small ({width}x{height})"

    if _is_blurry(img):
        return False, "image too blurry"

    face_ratio = _detect_face_ratio(img)
    if face_ratio > MAX_FACE_RATIO:
        pct = round(face_ratio * 100, 1)
        return False, f"face occupies {pct}% of the frame"

    body_ratio = _detect_body_ratio(img)
    if body_ratio > MAX_BODY_RATIO:
        pct = round(body_ratio * 100, 1)
        return False, f"full body occupies {pct}% of the frame"

    return True, ""


__all__ = ["check_image"]
