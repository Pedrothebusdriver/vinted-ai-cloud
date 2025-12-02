"""
Shared heuristics used by offline self-play and lightweight evaluation.

The goal is not to be perfect, but to mirror the simple rule-based behaviour
of the app so the teacher–student loop can record meaningful deltas in GBP.
"""

import json
import random
import re
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = Path("auto_heuristics_config.json")

# Fallback config used if the JSON file is missing; kept small to avoid drift.
DEFAULT_CONFIG: Dict[str, Any] = {
    "base_price_gbp": {"min": 8.0, "max": 45.0},
    "brand_price_overrides": {},
    "category_price_overrides": {},
    "condition_multipliers": {
        "New with tags": 1.25,
        "New": 1.15,
        "Excellent": 1.1,
        "Good used": 0.95,
        "Used": 0.9,
        "Fair": 0.8,
    },
    "brand_keywords": {},
    "colour_keywords": {},
    "condition_keywords": {},
    "size_keywords": {},
    "category_keywords": {},
}


def load_heuristics_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return DEFAULT_CONFIG.copy()
    except Exception:
        return DEFAULT_CONFIG.copy()


def _tokenise(text: str) -> Dict[str, int]:
    tokens = re.split(r"[^a-z0-9]+", text.lower())
    counts: Dict[str, int] = {}
    for token in tokens:
        if not token:
            continue
        counts[token] = counts.get(token, 0) + 1
    return counts


def _match_keyword(text: str, keyword_map: Dict[str, str]) -> Optional[str]:
    lowered = text.lower()
    for key, value in keyword_map.items():
        if key in lowered:
            return value
    return None


def _derive_range(config: Dict[str, Any], brand: Optional[str], category: Optional[str]) -> Dict[str, float]:
    if brand and brand in config.get("brand_price_overrides", {}):
        return config["brand_price_overrides"][brand]
    if category and category in config.get("category_price_overrides", {}):
        return config["category_price_overrides"][category]
    return config.get("base_price_gbp", {"min": 8.0, "max": 45.0})


def _apply_condition_multiplier(
    price_gbp: float, condition: Optional[str], config: Dict[str, Any]
) -> float:
    if not condition:
        return price_gbp
    multiplier = config.get("condition_multipliers", {}).get(condition)
    if multiplier is None:
        return price_gbp
    return price_gbp * float(multiplier)


def _estimate_price_gbp(
    listing: Dict[str, Any],
    brand: Optional[str],
    category: Optional[str],
    condition: Optional[str],
    config: Dict[str, Any],
    rng: Optional[random.Random] = None,
) -> float:
    rng = rng or random
    price_range = _derive_range(config, brand, category)
    low = float(price_range.get("min", 8.0))
    high = float(price_range.get("max", 45.0))
    mid = (low + high) / 2.0

    teacher_price = listing.get("price_gbp")
    if isinstance(teacher_price, (int, float)):
        # Blend the teacher price with the heuristic mid-point so the student
        # is plausible but not perfect.
        anchor = float(teacher_price)
        mid = (0.45 * anchor) + (0.55 * mid)

    conditioned = _apply_condition_multiplier(mid, condition, config)
    noise = rng.uniform(-0.12, 0.12)  # keep the student slightly imperfect
    guessed = max(1.0, conditioned * (1 + noise))
    return round(guessed, 2)


def infer_listing(
    listing: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    rng: Optional[random.Random] = None,
) -> Dict[str, Any]:
    config = config or load_heuristics_config()
    rng = rng or random

    title = str(listing.get("title") or "").strip()
    description = str(listing.get("description") or "").strip()
    blob = f"{title} {description}".strip()
    tokens = _tokenise(blob)
    token_text = " ".join(tokens.keys())

    brand = _match_keyword(token_text, config.get("brand_keywords", {})) or listing.get("brand")
    category = _match_keyword(token_text, config.get("category_keywords", {})) or listing.get("category")
    colour = _match_keyword(token_text, config.get("colour_keywords", {})) or listing.get("colour")
    condition = _match_keyword(token_text, config.get("condition_keywords", {})) or listing.get("condition")
    size = listing.get("size") or _match_keyword(token_text, config.get("size_keywords", {}))

    predicted_title = title or "Marketplace listing"
    if not title and brand:
        predicted_title = f"{brand} {category or 'item'}".strip()
    predicted_description = description or f"{brand or 'Item'} {category or ''} in {condition or 'good condition'}.".strip()

    price_gbp = _estimate_price_gbp(listing, brand, category, condition, config, rng=rng)

    return {
        "title": predicted_title,
        "description": predicted_description,
        "brand": brand,
        "size": size,
        "colour": colour,
        "condition": condition,
        "category": category,
        "price_gbp": price_gbp,
        "currency": "GBP",
    }


def infer_from_listing_text(
    title: str,
    description: Optional[str],
    price_gbp: Optional[float],
    category: Optional[str] = None,
    is_kids: Optional[bool] = None,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience wrapper to run heuristics on raw listing fields without reformatting callers.
    """
    listing = {
        "title": title or "",
        "description": description or "",
        "price_gbp": price_gbp,
        "category": category or ("kids" if is_kids else None),
    }
    return infer_listing(listing, config=config)


__all__ = ["infer_listing", "infer_from_listing_text", "load_heuristics_config"]
