"""Lightweight JSONL event log for the Pi app."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

EVENT_DIR = Path(os.getenv("EVENTS_DIR", "data/events"))
EVENT_DIR.mkdir(parents=True, exist_ok=True)


def _event_path(ts: datetime) -> Path:
    """Return the JSONL file for the supplied timestamp (UTC date)."""
    return EVENT_DIR / f"{ts.strftime('%Y-%m-%d')}.jsonl"


def record_event(kind: str, payload: Optional[Dict[str, Any]] = None) -> None:
    """
    Append a structured event to the daily JSONL log.

    Args:
        kind: Short event name, e.g., ``item_processed``.
        payload: Optional dictionary with event-specific data.
    """
    if not kind:
        return

    ts = datetime.now(timezone.utc)
    doc = {
        "ts": ts.isoformat(),
        "kind": kind,
        "payload": payload or {},
    }
    path = _event_path(ts)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False)
        fh.write("\n")


__all__ = ["record_event"]
