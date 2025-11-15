#!/usr/bin/env python3
"""
Wire Discord bridge inbox entries into the agent relay bus.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import List, Optional

from agent_relay import RelayStore  # type: ignore

BRIDGE_DIR = Path(".agent/discord-bridge")
INBOX_FILE = BRIDGE_DIR / "inbox" / "messages.jsonl"
STATE_PATH = BRIDGE_DIR / ".relay-state.json"


def _load_state() -> int:
    if not STATE_PATH.exists():
        return 0
    try:
        data = json.loads(STATE_PATH.read_text())
        return int(data.get("last_id", 0))
    except Exception:
        return 0


def _save_state(last_id: int) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"last_id": int(last_id)}))


def _iter_messages() -> List[dict]:
    if not INBOX_FILE.exists():
        return []
    entries = []
    with INBOX_FILE.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def process_once(agents: List[str], quiet: bool = False) -> int:
    last_id = _load_state()
    entries = _iter_messages()
    if not entries:
        return 0

    store = RelayStore()
    new_last = last_id
    forwarded = 0

    for entry in entries:
        snowflake = int(entry.get("id", "0"))
        if snowflake <= last_id:
            continue
        payload = {
            "ts": entry.get("created_at"),
            "kind": "discord_message",
            "message": entry.get("content"),
            "author": entry.get("author"),
            "channel_id": entry.get("channel_id"),
            "jump_url": entry.get("jump_url"),
            "attachments": entry.get("attachments", []),
        }
        store.append_message(payload, agents)
        new_last = max(new_last, snowflake)
        forwarded += 1
        if not quiet:
            logging.info("Forwarded %s to relay", snowflake)

    if forwarded:
        _save_state(new_last)
    return forwarded


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Push Discord bridge messages to agent relay inboxes.")
    parser.add_argument("--agents", default="codex-cli,codex-discord", help="Comma-separated agent ids.")
    parser.add_argument("--loop", action="store_true", help="Keep running and poll periodically.")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval when --loop is set.")
    parser.add_argument("--quiet", action="store_true", help="Suppress log output.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    if not agents:
        parser.error("At least one agent is required.")

    if not args.quiet:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.loop:
        while True:
            process_once(agents, quiet=args.quiet)
            time.sleep(args.interval)
    else:
        process_once(agents, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
