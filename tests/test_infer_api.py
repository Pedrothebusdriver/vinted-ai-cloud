import io
import sys
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PI_APP_DIR = ROOT / "pi-app"
if str(PI_APP_DIR) not in sys.path:
    sys.path.insert(0, str(PI_APP_DIR))

from app.main import app  # noqa: E402


def _make_image_bytes(colour=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", (64, 64), color=colour)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf.getvalue()


def test_infer_endpoint_returns_basic_fields(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("app.main.ocr.read_text", lambda _p: "ExampleCo M hoodie")
    client = TestClient(app)
    payload = _make_image_bytes()

    resp = client.post(
        "/api/infer",
        files={"file": ("test.jpg", payload, "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    for key in ["brand", "size", "colour", "category", "condition", "price_low", "price_mid", "price_high"]:
        assert key in data
    assert data["condition"] == "Good"


def test_infer_endpoint_uses_openai_stub(monkeypatch):
    called = {}

    async def fake_call(path: Path):
        called["path"] = str(path)
        return {
            "brand": "TestBrand",
            "size": "M",
            "colour": "Black",
            "category": "hoodie",
            "condition": "Used",
            "price_low": 10.0,
            "price_mid": 12.0,
            "price_high": 15.0,
            "source": "openai",
        }

    monkeypatch.setenv("OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("OPENAI_VISION_MODEL", "test-model")
    monkeypatch.setattr("app.main._call_openai_inference", fake_call)

    client = TestClient(app)
    resp = client.post(
        "/api/infer",
        files={"file": ("openai.jpg", _make_image_bytes((0, 0, 0)), "image/jpeg")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["brand"] == "TestBrand"
    assert data["price_mid"] == 12.0
    assert called
