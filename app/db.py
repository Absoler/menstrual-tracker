"""SQLite 数据访问：连接与建表。"""

import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = DATA_DIR / "tracker.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    date        TEXT NOT NULL,                 -- YYYY-MM-DD
    flow        TEXT NOT NULL DEFAULT 'none',
    colors      TEXT NOT NULL DEFAULT '[]',    -- JSON 数组
    clots       TEXT NOT NULL DEFAULT 'none',
    pain        TEXT NOT NULL DEFAULT 'none',
    symptoms    TEXT NOT NULL DEFAULT '[]',    -- JSON 数组
    mood        TEXT NOT NULL DEFAULT '[]',    -- JSON 数组
    medication  TEXT NOT NULL DEFAULT '',
    notes       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, date)
);
"""


def get_db() -> sqlite3.Connection:
    """返回一个行式连接；配合 with 语句使用会自动提交/回滚。"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.executescript(SCHEMA)
