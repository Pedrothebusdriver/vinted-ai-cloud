from __future__ import annotations

import sys
from pathlib import Path
from typing import List

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db, main  # type: ignore  # noqa
from app.core.models import Draft, DraftPhoto, PriceEstimate


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    db.init_db()
    for name in ("INP", "OUT", "BAK", "THUMBS", "INGEST_META"):
        path = tmp_path / name.lower()
        path.mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(main, name, path)
    yield


@pytest.fixture
def client(monkeypatch):
    client = TestClient(main.app)
    return client


@pytest.fixture
def stub_ingest(monkeypatch):
    async def fake_build_draft(*, item_id: int, filepaths: List[Path], metadata=None):
        photo = DraftPhoto(
            path=str(filepaths[0]),
            original_path=str(filepaths[0]),
            optimised_path=str(filepaths[0]),
        )
        return Draft(
            id=item_id,
            title="Stub Draft",
            brand="Nike",
            size="M",
            colour="Blue",
            category_id="123",
            category_name="Tops",
            condition="Good",
            price=PriceEstimate(low=5.0, mid=8.5, high=12.0),
            photos=[photo],
            metadata={"item_type": "top"},
        )

    monkeypatch.setattr(main.ingest_service, "build_draft", fake_build_draft)


def _upload_payload():
    return [
        ("files", ("shirt.jpg", b"fake-image-bytes", "image/jpeg")),
    ]


def test_create_and_fetch_draft(client, stub_ingest):
    resp = client.post("/api/drafts", files=_upload_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Stub Draft"
    draft_id = data["id"]

    list_resp = client.get("/api/drafts")
    assert list_resp.status_code == 200
    rows = list_resp.json()
    assert len(rows) == 1
    assert rows[0]["id"] == draft_id
    assert rows[0]["thumbnail_url"]

    detail_resp = client.get(f"/api/drafts/{draft_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["brand"] == "Nike"
    assert len(detail["photos"]) == 1
    assert detail["prices"]["mid"] == 8.5


def test_update_draft_fields(client, stub_ingest):
    resp = client.post("/api/drafts", files=_upload_payload())
    draft_id = resp.json()["id"]

    update_resp = client.put(
        f"/api/drafts/{draft_id}",
        json={"title": "Updated", "status": "ready", "price": 15.0},
    )
    assert update_resp.status_code == 200
    payload = update_resp.json()
    assert payload["title"] == "Updated"
    assert payload["status"] == "ready"
    assert payload["selected_price"] == 15.0
