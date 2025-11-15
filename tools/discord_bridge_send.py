#!/usr/bin/env python3
"""
Queue a reply for the Discord bridge bot by writing to `.agent/discord-bridge/outbox/`.
"""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

BRIDGE_DIR = Path(".agent/discord-bridge")
OUTBOX_DIR = BRIDGE_DIR / "outbox"
OUTBOX_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def queue_message(args: argparse.Namespace) -> Path:
    payload = {
        "id": uuid.uuid4().hex,
        "queued_at": _now(),
        "sender": args.sender,
        "content": args.message,
        "reply_to": args.reply_to,
        "channel_id": args.channel_id,
        "files": args.file or [],
    }
    filename = f"{int(datetime.now().timestamp())}-{payload['id']}.json"
    out_path = OUTBOX_DIR / filename
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Queue a Discord bridge message.")
    parser.add_argument("message", help="Message text to send.")
    parser.add_argument("--sender", help="Optional name to prefix in Discord.")
    parser.add_argument("--reply-to", help="Discord message ID to reply to.")
    parser.add_argument("--channel-id", type=int, help="Override channel id (defaults to first configured).")
    parser.add_argument("--file", action="append", help="Attach a local file (repeatable).")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    path = queue_message(args)
    print(f"Queued {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
