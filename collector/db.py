"""중앙 SQLite 저장소 접근 계층."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Mapping

_SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


def connect(path: str) -> sqlite3.Connection:
    """중앙 DB에 연결하고, 없으면 스키마를 생성한다."""
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn


def get_or_create_device(conn: sqlite3.Connection, name: str, os_str: str) -> int:
    """기기 이름으로 device id를 가져오거나 새로 만든다."""
    row = conn.execute("SELECT id FROM devices WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    cur = conn.execute(
        "INSERT INTO devices(name, os) VALUES(?, ?)", (name, os_str)
    )
    return int(cur.lastrowid)


def insert_visits(
    conn: sqlite3.Connection,
    device_id: int,
    browser: str,
    rows: Iterable[Mapping],
    source: str = "collector",
) -> int:
    """방문기록을 적재한다. UNIQUE 제약으로 중복은 자동 무시된다.

    반환값은 실제로 새로 저장된(중복이 아닌) 건수.
    """
    before = conn.total_changes
    conn.executemany(
        "INSERT OR IGNORE INTO visits"
        "(device_id, browser, url, domain, title, visit_time, source) "
        "VALUES(?, ?, ?, ?, ?, ?, ?)",
        [
            (
                device_id,
                browser,
                r["url"],
                r.get("domain"),
                r.get("title"),
                r["visit_time"],
                source,
            )
            for r in rows
        ],
    )
    return conn.total_changes - before
