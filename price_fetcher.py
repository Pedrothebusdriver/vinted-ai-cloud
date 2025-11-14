"""
Programmatic helper for fetching comparable Vinted prices.

This wraps the same scraping/API logic that powers the Flask cloud-helper
(`app.py`) so other scripts/agents can request comps without spinning up
an HTTP client.
"""

from typing import Any, Dict, Optional

try:
    # `app.get_comps` already handles caching, API fallbacks and HTML parsing.
    from app import get_comps  # type: ignore
except ImportError as exc:  # pragma: no cover - defensive guard
    raise RuntimeError("price_fetcher requires app.get_comps to be importable") from exc


def get_vinted_price(
    brand: str,
    item_type: str,
    size: Optional[str] = None,
    colour: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Return comparable pricing stats for the supplied attributes.

    Response example::
        {
            "query": "Nike hoodie M",
            "count": 32,
            "median": 18.5,
            "p25": 15.0,
            "p75": 22.0,
            "examples": [
                {"title": "...", "price_gbp": 18.0, "url": "..."},
                ...
            ],
            "source": "api"
        }
    """

    comps = get_comps(brand or "", item_type or "", size or "" if size else "", colour or "")
    if not comps or not comps.get("count"):
        return None
    return {
        "query": comps.get("query", ""),
        "count": comps.get("count", 0),
        "median": comps.get("median_price_gbp"),
        "p25": comps.get("p25_gbp"),
        "p75": comps.get("p75_gbp"),
        "examples": comps.get("examples", []),
        "source": comps.get("source", "api"),
        "clamp": comps.get("clamp", {}),
    }
