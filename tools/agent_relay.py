#!/usr/bin/env python3
"""
Minimal file-based relay so multiple Codex agents can chat via the Pi.

Usage:
    python tools/agent_relay.py send --author codex-cli --target codex-discord "Ping?"
    python tools/agent_relay.py pull --agent codex-discord --mark-read
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

import requests


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_dumps(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False)


@dataclass
class RelayStore:
    root: Path = field(default_factory=lambda: Path(".agent/relay"))

    def __post_init__(self) -> None:
        _ensure_dir(self.root)

    @property
    def log_path(self) -> Path:
        return self.root / "log.jsonl"

    def inbox_path(self, agent: str) -> Path:
        return self.root / f"inbox-{agent}.jsonl"

    def append_log(self, payload: dict) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(_json_dumps(payload) + "\n")

    def append_inbox(self, agent: str, payload: dict) -> None:
        path = self.inbox_path(agent)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(_json_dumps(payload) + "\n")

    def list_agents(self) -> List[str]:
        agents = []
        for path in self.root.glob("inbox-*.jsonl"):
            agents.append(path.stem.replace("inbox-", ""))
        return sorted(set(agents))

    def read_inbox(self, agent: str) -> List[dict]:
        path = self.inbox_path(agent)
        if not path.exists():
            return []
        items: List[dict] = []
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return items

    def clear_inbox(self, agent: str) -> None:
        path = self.inbox_path(agent)
        if path.exists():
            path.unlink()

    def append_message(self, payload: dict, recipients: Iterable[str]) -> None:
        payload = dict(payload)
        payload.setdefault("id", os.urandom(8).hex())
        payload.setdefault("ts", _utc_now())
        for agent in recipients:
            self.append_inbox(agent, payload)
        self.append_log(payload)


def _parse_agents(store: RelayStore, target: str, broadcast: bool) -> List[str]:
    if broadcast or target in {"codex-all", "all"}:
        agents = store.list_agents()
        if target not in agents and target not in ("codex-all", "all"):
            agents.append(target)
        return agents or [target]
    return [target]


def handle_send(args: argparse.Namespace) -> int:
    store = RelayStore()
    payload = {
        "id": os.urandom(8).hex(),
        "ts": _utc_now(),
        "author": args.author,
        "target": args.target,
        "message": args.message,
        "broadcast": bool(args.broadcast),
    }
    recipients = _parse_agents(store, args.target, args.broadcast)
    store.append_message(payload, recipients)

    webhook = args.webhook or os.getenv("AGENT_RELAY_WEBHOOK_URL")
    if webhook:
        try:
            requests.post(
                webhook,
                json={
                    "content": f"**{args.author} → {args.target}**: {args.message}",
                },
                timeout=5,
            )
        except requests.RequestException:
            pass

    print(f"Sent to {', '.join(recipients)}.")
    return 0


def _format_entry(entry: dict, output: str) -> str:
    if output == "json":
        return _json_dumps(entry)
    ts = entry.get("ts", "")
    author = entry.get("author", "?")
    msg = entry.get("message", "")
    return f"[{ts}] {author}: {msg}"


def handle_pull(args: argparse.Namespace) -> int:
    store = RelayStore()
    messages = store.read_inbox(args.agent)
    if args.limit:
        messages = messages[-args.limit :]
    for entry in messages:
        print(_format_entry(entry, args.output))
    if args.mark_read:
        store.clear_inbox(args.agent)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="File-based relay so agents can exchange JSON messages.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """Examples:
  python tools/agent_relay.py send --author codex-cli --target codex-discord "Ping?"
  python tools/agent_relay.py pull --agent codex-discord --mark-read"""
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    send = sub.add_parser("send", help="Send a message into the relay.")
    send.add_argument("message", help="Message text.")
    send.add_argument("--author", required=True, help="Author identifier (e.g., codex-cli).")
    send.add_argument("--target", default="codex-discord", help="Recipient identifier.")
    send.add_argument("--broadcast", action="store_true", help="Send to every inbox.")
    send.add_argument("--webhook", help="Override webhook URL for this send.")
    send.set_defaults(func=handle_send)

    pull = sub.add_parser("pull", help="Read messages from an inbox.")
    pull.add_argument("--agent", required=True, help="Agent identifier (e.g., codex-discord).")
    pull.add_argument("--limit", type=int, help="Only show the most recent N messages.")
    pull.add_argument(
        "--output",
        choices={"text", "json"},
        default="text",
        help="Display format.",
    )
    pull.add_argument("--mark-read", action="store_true", help="Clear inbox after reading.")
    pull.set_defaults(func=handle_pull)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
