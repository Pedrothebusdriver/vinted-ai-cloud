import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PI_APP_DIR = ROOT / "pi-app"
if str(PI_APP_DIR) not in sys.path:
    sys.path.insert(0, str(PI_APP_DIR))

from app import db  # noqa: E402
from app.main import app  # noqa: E402


def _seed_draft(tmp_path: Path) -> int:
    db.DB_PATH = tmp_path / "vinted.db"
    db.init_db()
    draft_id = 1
    with db.connect() as conn:
        conn.execute(
            "insert into drafts (item_id, title, description, brand, size, colour, category_id, category_name, condition, status, price_low_pence, price_mid_pence, price_high_pence, selected_price_pence, created_at, updated_at) "
            "values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                draft_id,
                "Test Coat",
                "Warm winter coat",
                "Arcteryx",
                "M",
                "Black",
                "outerwear",
                "Coats",
                "Good",
                "draft",
                5000,
                7000,
                9000,
                7500,
                db.now(),
                db.now(),
            ),
        )
        conn.execute(
            "insert into photos (draft_id, file_path, position) values (?, ?, ?)",
            (draft_id, "image1.jpg", 0),
        )
        conn.commit()
    return draft_id


def test_export_endpoint_returns_clipboard_payload(tmp_path):
    draft_id = _seed_draft(tmp_path)
    client = TestClient(app)

    response = client.get(f"/api/drafts/{draft_id}/export")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == draft_id
    assert data["title"] == "Test Coat"
    assert data["price"] == 75.0
    assert data["price_low"] == 50.0
    assert data["price_mid"] == 70.0
    assert data["price_high"] == 90.0
    assert data["clipboard"]["title"] == "Test Coat"
    assert "Brand: Arcteryx" in data["clipboard"]["description"]
    assert data["photos"][0]["position"] == 0
