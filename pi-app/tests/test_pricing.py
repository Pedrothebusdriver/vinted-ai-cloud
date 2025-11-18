import asyncio

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from core.pricing import PricingService


class FakeFetcher:
    def __init__(self):
        self.calls = 0

    def __call__(self, params):
        self.calls += 1
        return {
            "median_price_gbp": 120.0,
            "p25_gbp": 100.0,
            "p75_gbp": 150.0,
            "examples": [
                {"title": "Listing", "price_gbp": 120.0, "url": "https://vinted.example/listing"}
            ],
        }


def test_pricing_service_returns_clamped_values_and_caches():
    fetcher = FakeFetcher()
    service = PricingService(
        base_url="https://example.com",
        min_price_pence=500,
        max_price_pence=20000,
        cache_ttl_seconds=60,
        request_func=fetcher,
    )

    async def runner():
        estimate = await service.suggest_price(brand="Nike", category="hoodie", size="M")
        assert estimate.mid == pytest.approx(120.0)
        assert estimate.low == pytest.approx(100.0)
        assert estimate.high == pytest.approx(150.0)
        assert estimate.examples

        # Cached call should not invoke fetcher again
        estimate_cached = await service.suggest_price(brand="Nike", category="hoodie", size="M")
        assert estimate_cached.mid == pytest.approx(120.0)
        assert fetcher.calls == 1

    asyncio.run(runner())
