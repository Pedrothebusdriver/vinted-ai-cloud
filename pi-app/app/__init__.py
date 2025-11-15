"""
Utility package initialiser for the Pi FastAPI app.

Exposes key submodules so `from app import compliance, events` works even when
the app folder is imported as a package (e.g., `uvicorn app.main:app`).
"""

from . import classifier, compliance, db, events, export, ocr  # noqa: F401

__all__ = [
    "classifier",
    "compliance",
    "db",
    "events",
    "export",
    "ocr",
]
