"""SQLite connection handling and versioned schema migrations."""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings

# Append-only list. Index + 1 == schema version stored in PRAGMA user_version.
MIGRATIONS: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        dedupe_key TEXT UNIQUE,
        brand_name TEXT, platform TEXT, source_url TEXT, brand_domain TEXT, niche TEXT,
        contact_email TEXT DEFAULT '', decision_maker TEXT DEFAULT '', first_name TEXT DEFAULT '',
        intent_score INTEGER DEFAULT 50, competition_level TEXT DEFAULT 'Low',
        raw_snippet TEXT DEFAULT '', hook_concepts TEXT DEFAULT '',
        email_subject TEXT DEFAULT '', step1_body TEXT DEFAULT '', step2_body TEXT DEFAULT '', step3_body TEXT DEFAULT '',
        status TEXT DEFAULT 'New', sequence_step INTEGER DEFAULT 0,
        replied INTEGER DEFAULT 0, bounced INTEGER DEFAULT 0, unsubscribed INTEGER DEFAULT 0, is_demo INTEGER DEFAULT 0,
        first_sent_at TEXT DEFAULT '', last_sent_at TEXT DEFAULT '', next_followup_at TEXT DEFAULT '',
        message_id_header TEXT DEFAULT '', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS suppression (email TEXT PRIMARY KEY, reason TEXT, added_at TEXT);
    CREATE TABLE IF NOT EXISTS send_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER, step INTEGER,
        recipient TEXT, sent_date TEXT, sent_at TEXT, live INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_leads_followup ON leads(next_followup_at);
    CREATE INDEX IF NOT EXISTS idx_send_logs_date ON send_logs(sent_date);
    CREATE INDEX IF NOT EXISTS idx_send_logs_recipient ON send_logs(recipient);
    """,
    """
    CREATE TABLE IF NOT EXISTS job_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, requested_at TEXT NOT NULL, done_at TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """,
]


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    path = get_settings().db_path
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> int:
    """Apply any pending migrations. Safe to call from several processes. Returns schema version."""
    with connect() as c:
        version = c.execute("PRAGMA user_version").fetchone()[0]
        for i, sql in enumerate(MIGRATIONS[version:], start=version + 1):
            c.executescript(sql)
            c.execute(f"PRAGMA user_version = {i}")
        return len(MIGRATIONS)
