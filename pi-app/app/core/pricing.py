from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple, Union

import httpx

from .models import PriceEstimate

logger = logging.getLogger(__name__)

RequestFunc = Union[
    Callable[[Dict[str, str]], Awaitable[Optional[Dict[str, Any]]]],
    Callable[[Dict[str, str]], Optional[Dict[str, Any]]],
]
TimeFunc = Callable[[], float]


class PricingService:
    def __init__(
        self,
        base_url: str,
        min_price_pence: int,
        max_price_pence: int,
        *,
        cache_ttl_seconds: int = 600,
        request_func: Optional[RequestFunc] = None,
        time_func: Optional[TimeFunc] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.min_price = max(0.0, min_price_pence / 100.0)
        self.max_price = max(self.min_price, max_price_pence / 100.0)
        self.cache_ttl = cache_ttl_seconds
        self._request_func = request_func
        self._time_fn = time_func or time.time
        self._cache: Dict[Tuple[str, str, str, str], Tuple[float, PriceEstimate]] = {}
        self._lock = asyncio.Lock()

    async def suggest_price(
        self,
        *,
        brand: Optional[str] = None,
        category: Optional[str] = None,
        size: Optional[str] = None,
        condition: Optional[str] = None,
        colour: Optional[str] = None,
    ) -> PriceEstimate:
        if not self.base_url:
            return PriceEstimate()
        key = (
            (brand or "").strip().lower(),
            (category or "").strip().lower(),
            (size or "").strip().lower(),
            (condition or "").strip().lower(),
        )
        async with self._lock:
            cached = self._cache.get(key)
            if cached and cached[0] > self._time_fn():
                return cached[1]

        params = {
            "brand": brand or "",
            "item_type": category or "",
            "size": size or "",
            "colour": colour or "",
            "condition": condition or "",
        }
        payload = await self._fetch_remote(params)
        estimate = self._build_estimate(payload)

        async with self._lock:
            self._cache[key] = (self._time_fn() + self.cache_ttl, estimate)
        return estimate

    async def _fetch_remote(self, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        if not self.base_url:
            return None
        if self._request_func:
            result = self._request_func(params)
            if inspect.isawaitable(result):
                result = await result  # type: ignore[assignment]
            return result
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                for path in ("/api/price", "/price"):
                    url = f"{self.base_url}{path}"
                    resp = await client.get(url, params=params)
                    if resp.status_code == 200:
                        return resp.json()
        except Exception as exc:  # pragma: no cover - network
            logger.warning("pricing_fetch_failed", error=str(exc))
        return None

    def _build_estimate(self, payload: Optional[Dict[str, Any]]) -> PriceEstimate:
        if not payload:
            return PriceEstimate()
        try:
            low = self._clamp_float(payload.get("p25_gbp"))
            mid = self._clamp_float(payload.get("median_price_gbp"))
            high = self._clamp_float(payload.get("p75_gbp"))
        except (TypeError, ValueError):
            low = mid = high = None
        examples = payload.get("examples", []) if isinstance(payload, dict) else []
        return PriceEstimate(low=low, mid=mid, high=high, examples=examples[:5])

    def _clamp_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if number <= 0:
            return None
        return max(self.min_price, min(self.max_price, number))


def build_default_service() -> PricingService:
    base = os.getenv("COMPS_BASE_URL", "")
    min_price = int(os.getenv("VINTED_PRICE_MIN_PENCE", "50"))
    max_price = int(os.getenv("VINTED_PRICE_MAX_PENCE", "50000"))
    return PricingService(base, min_price, max_price)
