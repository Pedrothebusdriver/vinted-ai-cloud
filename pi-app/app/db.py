from pathlib import Path
import sqlite3, time

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
      width INTEGER, height INTEGER, is_label INTEGER DEFAULT 0
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
      price_pence INTEGER
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

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connect() as c:
        for s in SCHEMA:
            c.execute(s)
        c.commit()

def now() -> int:
    return int(time.time())
