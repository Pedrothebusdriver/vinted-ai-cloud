#!/usr/bin/env python3
"""
Bridge Discord channels into `.agent/discord-bridge/` for Codex agents.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import os
import shutil
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import discord
import httpx

BRIDGE_DIR = Path(".agent/discord-bridge")
INBOX_DIR = BRIDGE_DIR / "inbox"
OUTBOX_DIR = BRIDGE_DIR / "outbox"
SENT_DIR = BRIDGE_DIR / "sent"
FAILED_DIR = BRIDGE_DIR / "failed"
ATTACH_DIR = BRIDGE_DIR / "attachments"
INBOX_FILE = INBOX_DIR / "messages.jsonl"

for path in (INBOX_DIR, OUTBOX_DIR, SENT_DIR, FAILED_DIR, ATTACH_DIR):
    path.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(path: Path, data: dict) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _jsonl_append(path: Path, data: dict) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(data, ensure_ascii=False) + "\n")


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class BridgeConfig:
    token: str
    channel_ids: List[int]
    allowed_user_ids: List[int] = field(default_factory=list)
    forward_url: Optional[str] = None
    forward_token: Optional[str] = None
    download_attachments: bool = True
    outbox_poll_seconds: float = 2.0

    @classmethod
    def load(cls) -> "BridgeConfig":
        config_path = os.getenv("DISCORD_BRIDGE_CONFIG", str(Path.home() / "secrets/discord_bot.json"))
        payload = {}
        if config_path and Path(config_path).expanduser().exists():
            payload = json.loads(Path(config_path).expanduser().read_text())

        token = os.getenv("DISCORD_BRIDGE_TOKEN") or payload.get("token")
        channels = os.getenv("DISCORD_BRIDGE_CHANNELS")
        if channels:
            channel_ids = [int(c.strip()) for c in channels.split(",") if c.strip().isdigit()]
        else:
            channel_ids = [int(c) for c in payload.get("channel_ids", [])]

        allowed = os.getenv("DISCORD_BRIDGE_ALLOW_USERS")
        if allowed:
            allowed_users = [int(u.strip()) for u in allowed.split(",") if u.strip().isdigit()]
        else:
            allowed_users = [int(u) for u in payload.get("allowed_user_ids", [])]

        forward_url = os.getenv("DISCORD_BRIDGE_FORWARD_URL") or payload.get("forward_url")
        forward_token = os.getenv("DISCORD_BRIDGE_FORWARD_TOKEN") or payload.get("forward_token")
        download = _env_bool("DISCORD_BRIDGE_SAVE_ATTACHMENTS", payload.get("download_attachments", True))

        if not token or not channel_ids:
            raise SystemExit("Discord bridge requires a bot token and at least one channel id.")

        poll_seconds = float(os.getenv("DISCORD_BRIDGE_OUTBOX_POLL", payload.get("outbox_poll_seconds", 2.0)))

        return cls(
            token=token,
            channel_ids=channel_ids,
            allowed_user_ids=allowed_users,
            forward_url=forward_url,
            forward_token=forward_token,
            download_attachments=download,
            outbox_poll_seconds=poll_seconds,
        )


class BridgeBot(discord.Client):
    def __init__(self, config: BridgeConfig):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.outbox_task: Optional[asyncio.Task] = None

    async def setup_hook(self) -> None:
        self.outbox_task = asyncio.create_task(self.outbox_worker())

    async def close(self) -> None:
        if self.outbox_task:
            self.outbox_task.cancel()
        await super().close()

    async def on_ready(self) -> None:
        logging.info(
            "Bridge ready as %s (channels=%s)",
            self.user,
            ",".join(str(cid) for cid in self.config.channel_ids),
        )

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        if message.channel.id not in self.config.channel_ids:
            return
        if self.config.allowed_user_ids and message.author.id not in self.config.allowed_user_ids:
            return

        payload = await self._build_payload(message)
        self._persist_payload(payload)
        if self.config.forward_url:
            await self._forward_payload(payload)

    async def _build_payload(self, message: discord.Message) -> dict:
        attachments = []
        if self.config.download_attachments:
            for attachment in message.attachments:
                target_dir = ATTACH_DIR / str(message.id)
                target_dir.mkdir(parents=True, exist_ok=True)
                dest = target_dir / attachment.filename
                await attachment.save(dest)
                attachments.append({"filename": attachment.filename, "path": str(dest), "url": attachment.url})
        else:
            attachments = [
                {"filename": attachment.filename, "url": attachment.url} for attachment in message.attachments
            ]

        return {
            "id": str(message.id),
            "channel_id": message.channel.id,
            "channel_name": getattr(message.channel, "name", ""),
            "author": {
                "id": message.author.id,
                "name": str(message.author),
                "display": message.author.display_name,
            },
            "content": message.content,
            "clean_content": message.clean_content,
            "jump_url": message.jump_url,
            "created_at": message.created_at.isoformat(),
            "attachments": attachments,
        }

    def _persist_payload(self, payload: dict) -> None:
        INBOX_DIR.mkdir(parents=True, exist_ok=True)
        _json_dump(INBOX_DIR / f"{payload['id']}.json", payload)
        _jsonl_append(INBOX_FILE, payload)

    async def _forward_payload(self, payload: dict) -> None:
        data = dict(payload)
        headers = {}
        if self.config.forward_token:
            headers["Authorization"] = self.config.forward_token
        async with httpx.AsyncClient(timeout=5) as client:
            with contextlib.suppress(Exception):
                await client.post(self.config.forward_url, json=data, headers=headers)

    async def outbox_worker(self) -> None:
        while True:
            try:
                for path in sorted(OUTBOX_DIR.glob("*.json")):
                    await self._send_outbound(path)
            except Exception as exc:  # pragma: no cover - runtime guard
                logging.exception("Outbox worker error: %s", exc)
            await asyncio.sleep(self.config.outbox_poll_seconds)

    async def _send_outbound(self, path: Path) -> None:
        payload = json.loads(path.read_text())
        channel_id = int(payload.get("channel_id") or self.config.channel_ids[0])
        channel = self.get_channel(channel_id) or await self.fetch_channel(channel_id)

        content = payload.get("content") or ""
        sender = payload.get("sender")
        if sender:
            content = f"[{sender}] {content}"

        reply_to = payload.get("reply_to")
        reference = None
        if reply_to:
            with contextlib.suppress(Exception):
                msg = await channel.fetch_message(int(reply_to))
                reference = msg.to_reference()

        files = []
        for file_path in payload.get("files", []):
            file_path = Path(file_path)
            if file_path.exists():
                files.append(discord.File(str(file_path)))

        try:
            await channel.send(content, reference=reference, files=files or None)
            shutil.move(str(path), SENT_DIR / path.name)
        except Exception as exc:
            logging.warning("Failed to send outbound message %s: %s", path.name, exc)
            shutil.move(str(path), FAILED_DIR / path.name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mirror Discord chat into .agent/discord-bridge/",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """Env vars:
  DISCORD_BRIDGE_TOKEN               - bot token (overrides JSON file)
  DISCORD_BRIDGE_CHANNELS            - comma-separated channel IDs
  DISCORD_BRIDGE_ALLOW_USERS         - optional whitelist of user IDs
  DISCORD_BRIDGE_FORWARD_URL         - optional webhook/HTTP endpoint
  DISCORD_BRIDGE_SAVE_ATTACHMENTS    - set to 0 to skip attachment downloads
"""
        ),
    )
    return parser


def main() -> int:
    build_parser().parse_args()
    config = BridgeConfig.load()
    client = BridgeBot(config)
    client.run(config.token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
