#!/usr/bin/env python3
"""
Helper to align the Pi SQLite schema with the FlipLens MVP requirements.

- Ensures the drafts table exposes the richer columns (brand/size/etc).
- Ensures the photos table has draft-linked metadata (draft_id/file_path/position).

Usage:
    python scripts/sqlite_migrate.py --db pi-app/data/vinted.db
    python scripts/sqlite_migrate.py --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import Iterable, List

DRAFTS_SQL = """
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    status TEXT DEFAULT 'draft',
    brand TEXT,
    size TEXT,
    colour TEXT,
    category_id TEXT,
    condition TEXT,
    title TEXT,
    description TEXT,
    price_low INTEGER,
    price_mid INTEGER,
    price_high INTEGER,
    selected_price INTEGER
);
"""

PHOTOS_SQL = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    original_path TEXT,
    optimised_path TEXT,
    width INTEGER,
    height INTEGER,
    is_label INTEGER DEFAULT 0
);
"""

REQUIRED_DRAFT_COLUMNS: List[str] = [
    "id",
    "created_at",
    "updated_at",
    "status",
    "brand",
    "size",
    "colour",
    "category_id",
    "condition",
    "title",
    "description",
    "price_low",
    "price_mid",
    "price_high",
    "selected_price",
]

REQUIRED_PHOTO_COLUMNS = {
    "draft_id": "INTEGER",
    "file_path": "TEXT",
    "position": "INTEGER",
}


def run_sql(conn: sqlite3.Connection, sql: str, *, dry_run: bool) -> None:
    statement = " ".join(sql.strip().split())
    print(f"[sql] {statement}")
    if not dry_run:
        conn.execute(sql)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def table_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def ensure_drafts_table(conn: sqlite3.Connection, *, dry_run: bool) -> None:
    if not table_exists(conn, "drafts"):
        print("[info] drafts table missing – creating fresh schema.")
        run_sql(conn, DRAFTS_SQL, dry_run=dry_run)
        return

    columns = table_columns(conn, "drafts")
    missing: List[str] = [c for c in REQUIRED_DRAFT_COLUMNS if c not in columns]

    if not missing and columns and columns[0] == "id":
        print("[ok] drafts table already exposes the FlipLens schema.")
        return

    print(
        "[warn] drafts table missing columns "
        f"{missing or '[id primary key not present]'} – rebuilding."
    )
    timestamp = int(time.time())

    run_sql(conn, "ALTER TABLE drafts RENAME TO drafts__legacy", dry_run=dry_run)
    run_sql(conn, DRAFTS_SQL, dry_run=dry_run)

    if not dry_run:
        legacy_cols = table_columns(conn, "drafts__legacy")
    else:
        legacy_cols = columns

    can_copy_minimal = all(col in legacy_cols for col in ("item_id", "title"))
    if can_copy_minimal:
        sql = """
            INSERT INTO drafts (
                id, title, selected_price, created_at, updated_at, status
            )
            SELECT
                item_id,
                title,
                COALESCE(price_pence, NULL),
                :ts,
                :ts,
                'draft'
            FROM drafts__legacy
        """
        print("[info] migrating existing rows from drafts__legacy.")
        if not dry_run:
            conn.execute(sql, {"ts": timestamp})
    else:
        print("[info] no legacy drafts data found to migrate.")

    run_sql(conn, "DROP TABLE drafts__legacy", dry_run=dry_run)


def ensure_photos_table(conn: sqlite3.Connection, *, dry_run: bool) -> None:
    if not table_exists(conn, "photos"):
        print("[info] photos table missing – creating fresh schema.")
        run_sql(conn, PHOTOS_SQL, dry_run=dry_run)
        return

    columns = table_columns(conn, "photos")
    for column, col_type in REQUIRED_PHOTO_COLUMNS.items():
        if column not in columns:
            run_sql(
                conn,
                f"ALTER TABLE photos ADD COLUMN {column} {col_type}",
                dry_run=dry_run,
            )
            if column == "draft_id":
                run_sql(
                    conn,
                    "UPDATE photos SET draft_id = COALESCE(draft_id, item_id)",
                    dry_run=dry_run,
                )

    columns = table_columns(conn, "photos")
    if "file_path" in columns:
        print("[ok] photos table already records FlipLens metadata.")


def vacuum(conn: sqlite3.Connection, *, dry_run: bool) -> None:
    print("[info] vacuuming database for consistency.")
    run_sql(conn, "VACUUM", dry_run=dry_run)


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FlipLens SQLite migration helper.")
    parser.add_argument(
        "--db",
        default="pi-app/data/vinted.db",
        help="Path to the SQLite database (default: pi-app/data/vinted.db)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the SQL that would run without applying it.",
    )
    return parser.parse_args(list(argv))


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"[warn] {db_path} does not exist yet; creating parent directories.")
        if not args.dry_run:
            db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        ensure_drafts_table(conn, dry_run=args.dry_run)
        ensure_photos_table(conn, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
        vacuum(conn, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
