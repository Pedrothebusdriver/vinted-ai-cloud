#!/usr/bin/env python3
"""
Stream relay inbox entries in near real-time.

Useful for agents that want push-style notifications instead of polling.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from typing import Optional

import requests

from agent_relay import RelayStore  # type: ignore


def _deliver_exec(command: str, payload: dict) -> None:
    proc = subprocess.Popen(
        command if isinstance(command, str) else shlex.split(command),
        shell=isinstance(command, str),
        stdin=subprocess.PIPE,
    )
    if proc.stdin:
        proc.stdin.write(json.dumps(payload).encode())
        proc.stdin.close()
    proc.wait()


def _deliver_http(url: str, payload: dict) -> None:
    try:
        requests.post(url, json=payload, timeout=5)
    except requests.RequestException:
        pass


def stream_loop(args: argparse.Namespace) -> None:
    store = RelayStore()
    quiet = args.quiet
    interval = args.interval

    while True:
        messages = store.read_inbox(args.agent)
        if messages:
            remaining = messages.copy()
            for entry in messages:
                if not quiet:
                    print(json.dumps(entry, ensure_ascii=False), flush=True)
                if args.exec:
                    _deliver_exec(args.exec, entry)
                if args.http:
                    _deliver_http(args.http, entry)
                remaining.pop(0)
                if not args.no_ack:
                    path = store.inbox_path(args.agent)
                    if remaining:
                        with path.open("w", encoding="utf-8") as fh:
                            for item in remaining:
                                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
                    else:
                        store.clear_inbox(args.agent)
            if args.once:
                break
        if args.once:
            break
        time.sleep(interval)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stream relay inbox entries.")
    parser.add_argument("--agent", required=True, help="Agent identifier (e.g., codex-discord).")
    parser.add_argument("--interval", type=float, default=2.0, help="Poll interval in seconds.")
    parser.add_argument("--exec", help="Command to execute per entry (payload piped to stdin).")
    parser.add_argument("--http", help="HTTP endpoint to POST each entry to.")
    parser.add_argument("--no-ack", action="store_true", help="Do not remove entries after delivery.")
    parser.add_argument("--quiet", action="store_true", help="Suppress stdout printing.")
    parser.add_argument("--once", action="store_true", help="Process current inbox and exit.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    stream_loop(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
