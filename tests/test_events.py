import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pi-app"))

from app import events  # noqa: E402


@pytest.fixture()
def temp_event_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(events, "EVENT_DIR", tmp_path)
    events.EVENT_DIR.mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_record_event_writes_daily_file(temp_event_dir, monkeypatch):
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2025, 11, 17, 12, 30, tzinfo=timezone.utc)

    monkeypatch.setattr(events, "datetime", FrozenDatetime)

    events.record_event("upload_ok", {"item_id": 42})
    path = temp_event_dir / "2025-11-17.jsonl"
    data = path.read_text().strip().splitlines()
    assert len(data) == 1
    doc = json.loads(data[0])
    assert doc["kind"] == "upload_ok"
    assert doc["payload"] == {"item_id": 42}
    assert doc["ts"].startswith("2025-11-17T12:30:00")


def test_list_events_returns_newest_first(temp_event_dir):
    older = temp_event_dir / "2025-11-16.jsonl"
    older.write_text('{"ts":"2025-11-16T10:00:00Z","kind":"old","payload":{"seq":1}}\n')
    newer = temp_event_dir / "2025-11-17.jsonl"
    newer.write_text(
        '{"ts":"2025-11-17T09:00:00Z","kind":"mid","payload":{"seq":2}}\n'
        '{"ts":"2025-11-17T12:00:00Z","kind":"new","payload":{"seq":3}}\n'
    )

    items = events.list_events(limit=2)
    assert [e["kind"] for e in items] == ["new", "mid"]
    assert items[0]["payload"]["seq"] == 3
