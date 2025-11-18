import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
PI_APP_DIR = ROOT / "pi-app"
if str(PI_APP_DIR) not in sys.path:
    sys.path.insert(0, str(PI_APP_DIR))

from app.main import APP_VERSION, app  # noqa: E402


def test_health_includes_status_version_and_uptime():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == APP_VERSION
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0
