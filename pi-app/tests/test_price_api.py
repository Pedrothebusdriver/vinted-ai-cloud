from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import main  # type: ignore  # noqa: E402
from app.core.models import PriceEstimate  # type: ignore  # noqa: E402


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def stub_price(monkeypatch):
    recorded = {}

    async def fake_suggest_price(**kwargs):
        recorded["kwargs"] = kwargs
        return PriceEstimate(
            low=10.0,
            mid=12.5,
            high=15.0,
            examples=[{"title": "Example listing", "price_gbp": 12.5, "url": "https://vinted.example/item"}],
        )

    monkeypatch.setattr(main, "pricing_service", SimpleNamespace(suggest_price=fake_suggest_price))
    return recorded


def test_price_endpoint_returns_estimate(client, stub_price):
    payload = {
        "brand": "Nike",
        "item_type": "hoodie",
        "size": "M",
        "colour": "Black",
        "condition": "Fair",
    }
    resp = client.post("/api/price", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["mid"] == pytest.approx(12.5)
    assert data["examples"]
    assert stub_price["kwargs"]["condition"] == "Fair"
    assert stub_price["kwargs"]["category"] == "hoodie"


def test_price_endpoint_handles_empty_payload(client, monkeypatch):
    async def fake_suggest_price(**kwargs):
        return PriceEstimate()

    monkeypatch.setattr(main, "pricing_service", SimpleNamespace(suggest_price=fake_suggest_price))
    resp = client.post("/api/price", json={})
    assert resp.status_code == 200
    assert resp.json() == {"low": None, "mid": None, "high": None, "examples": []}
