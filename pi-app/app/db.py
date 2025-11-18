import sqlite3
import time
from pathlib import Path

DB_PATH = Path('data') / 'vinted.db'

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      status TEXT DEFAULT 'draft',
      created_at INTEGER, updated_at INTEGER
    );""",
    """CREATE TABLE IF NOT EXISTS photos (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      item_id INTEGER,
      original_path TEXT, optimised_path TEXT,
      width INTEGER, height INTEGER, is_label INTEGER DEFAULT 0,
      draft_id INTEGER,
      file_path TEXT,
      position INTEGER DEFAULT 0
    );""",
    """CREATE TABLE IF NOT EXISTS attributes (
      item_id INTEGER,
      field TEXT,
      value TEXT,
      confidence TEXT
    );""",
    """CREATE TABLE IF NOT EXISTS drafts (
      item_id INTEGER PRIMARY KEY,
      title TEXT,
      price_pence INTEGER,
      description TEXT,
      brand TEXT,
      size TEXT,
      colour TEXT,
      category_id TEXT,
      category_name TEXT,
      condition TEXT,
      status TEXT DEFAULT 'draft',
      price_low_pence INTEGER,
      price_mid_pence INTEGER,
      price_high_pence INTEGER,
      selected_price_pence INTEGER,
      created_at INTEGER,
      updated_at INTEGER
    );""",
    """CREATE TABLE IF NOT EXISTS prices (
      item_id INTEGER,
      recommended_pence INTEGER,
      p25_pence INTEGER,
      p75_pence INTEGER,
      checked_at INTEGER
    );""",
    """CREATE TABLE IF NOT EXISTS comps (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      item_id INTEGER,
      title TEXT,
      price_pence INTEGER,
      url TEXT
    );"""
]

EXTRA_COLUMNS = {
    "drafts": [
        ("description", "TEXT"),
        ("brand", "TEXT"),
        ("size", "TEXT"),
        ("colour", "TEXT"),
        ("category_id", "TEXT"),
        ("category_name", "TEXT"),
        ("condition", "TEXT"),
        ("status", "TEXT DEFAULT 'draft'"),
        ("price_low_pence", "INTEGER"),
        ("price_mid_pence", "INTEGER"),
        ("price_high_pence", "INTEGER"),
        ("selected_price_pence", "INTEGER"),
        ("created_at", "INTEGER"),
        ("updated_at", "INTEGER"),
    ],
    "photos": [
        ("draft_id", "INTEGER"),
        ("file_path", "TEXT"),
        ("position", "INTEGER DEFAULT 0"),
    ],
}

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        for s in SCHEMA:
            c.execute(s)
        _ensure_extra_columns(c)
        c.commit()

def now() -> int:
    return int(time.time())

def _ensure_extra_columns(conn):
    for table, columns in EXTRA_COLUMNS.items():
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
        for column, ddl in columns:
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
