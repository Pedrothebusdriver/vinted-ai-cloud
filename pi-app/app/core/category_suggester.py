from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Sequence

from rapidfuzz import fuzz

from .models import CategorySuggestion

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DATA_PATH = Path(os.getenv("VINTED_CATEGORIES_PATH", _REPO_ROOT / "data" / "vinted_categories.json"))


def _normalise_keywords(keywords: Iterable[str]) -> List[str]:
    return [kw.strip().lower() for kw in keywords if kw and kw.strip()]


@lru_cache(maxsize=1)
def _load_categories() -> List[dict]:
    if not _DATA_PATH.exists():
        return []
    raw = json.loads(_DATA_PATH.read_text())
    categories: List[dict] = []
    for entry in raw:
        categories.append(
            {
                "id": str(entry.get("id", "")),
                "name": str(entry.get("name", "")),
                "keywords": _normalise_keywords(entry.get("keywords", [])),
            }
        )
    return categories


def _compose_blob(parts: Sequence[str]) -> str:
    return " ".join([p for p in parts if p]).lower()


def suggest_categories(
    hint_text: str | None = None,
    ocr_text: str | None = None,
    filename: str | None = None,
    *,
    limit: int = 5,
) -> List[CategorySuggestion]:
    """Return ranked categories based on the provided hints."""

    categories = _load_categories()
    if not categories:
        return []

    blob = _compose_blob((hint_text, ocr_text, filename))
    if not blob:
        return []

    scored: List[CategorySuggestion] = []
    for entry in categories:
        base_score = fuzz.partial_ratio(blob, entry["name"].lower())
        keyword_bonus = 0
        for kw in entry["keywords"]:
            if kw and kw in blob:
                keyword_bonus = 25
                break
        score = base_score * 0.7 + keyword_bonus
        if score <= 0:
            continue
        scored.append(
            CategorySuggestion(
                id=entry["id"],
                name=entry["name"],
                score=round(score, 2),
                keywords=list(entry["keywords"]),
            )
        )

    scored.sort(key=lambda item: item.score, reverse=True)
    return scored[: max(1, limit)]
