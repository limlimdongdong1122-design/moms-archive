"""중앙 DB 조회 / 집계 / 비교 / 수집 로직 (순수 함수 → 테스트 용이)."""

from __future__ import annotations

import sqlite3
from itertools import groupby

from collector import db


def open_conn(path: str) -> sqlite3.Connection:
    """스키마를 보장하고 row_factory를 설정한 연결을 돌려준다."""
    conn = db.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ph(n: int) -> str:
    return ",".join("?" * n)


# ── 목록 ──────────────────────────────────────────────────────────

def list_devices(conn):
    rows = conn.execute(
        "SELECT d.id, d.name, d.os, COUNT(v.id) AS visits "
        "FROM devices d LEFT JOIN visits v ON v.device_id = d.id "
        "GROUP BY d.id ORDER BY d.name"
    )
    return [dict(r) for r in rows]


def list_browsers(conn):
    rows = conn.execute(
        "SELECT browser, COUNT(*) AS visits FROM visits "
        "GROUP BY browser ORDER BY visits DESC"
    )
    return [dict(r) for r in rows]


# ── 필터 ──────────────────────────────────────────────────────────

def _filter(device_ids, browsers, start, end, q):
    where, params = [], []
    if device_ids:
        where.append(f"v.device_id IN ({_ph(len(device_ids))})")
        params += [int(x) for x in device_ids]
    if browsers:
        where.append(f"v.browser IN ({_ph(len(browsers))})")
        params += list(browsers)
    if start is not None:
        where.append("v.visit_time >= ?")
        params.append(int(start))
    if end is not None:
        where.append("v.visit_time < ?")
        params.append(int(end))
    if q:
        where.append("(v.url LIKE ? OR v.title LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    return clause, params


def query_visits(conn, *, device_ids=None, browsers=None, start=None, end=None,
                 q=None, limit=200, offset=0):
    clause, params = _filter(device_ids, browsers, start, end, q)
    items = [dict(r) for r in conn.execute(
        "SELECT v.id, d.name AS device, v.device_id, v.browser, v.url, v.domain, "
        "v.title, v.visit_time "
        "FROM visits v JOIN devices d ON v.device_id = d.id "
        f"{clause} ORDER BY v.visit_time DESC LIMIT ? OFFSET ?",
        params + [int(limit), int(offset)],
    )]
    total = conn.execute(f"SELECT COUNT(*) FROM visits v {clause}", params).fetchone()[0]
    return {"total": total, "items": items}


def stats(conn, *, device_ids=None, browsers=None, start=None, end=None, q=None):
    clause, params = _filter(device_ids, browsers, start, end, q)
    total = conn.execute(f"SELECT COUNT(*) FROM visits v {clause}", params).fetchone()[0]
    per_browser = [dict(r) for r in conn.execute(
        f"SELECT v.browser, COUNT(*) AS count FROM visits v {clause} "
        "GROUP BY v.browser ORDER BY count DESC", params)]
    per_device = [dict(r) for r in conn.execute(
        "SELECT d.name AS device, COUNT(*) AS count "
        "FROM visits v JOIN devices d ON v.device_id = d.id "
        f"{clause} GROUP BY d.name ORDER BY count DESC", params)]
    per_day = [dict(r) for r in conn.execute(
        "SELECT date(v.visit_time, 'unixepoch', 'localtime') AS day, COUNT(*) AS count "
        f"FROM visits v {clause} GROUP BY day ORDER BY day", params)]
    domain_where = f"{clause} {'AND' if clause else 'WHERE'} v.domain IS NOT NULL"
    top_domains = [dict(r) for r in conn.execute(
        f"SELECT v.domain, COUNT(*) AS count FROM visits v {domain_where} "
        "GROUP BY v.domain ORDER BY count DESC LIMIT 15", params)]
    return {
        "total": total,
        "per_browser": per_browser,
        "per_device": per_device,
        "per_day": per_day,
        "top_domains": top_domains,
    }


# ── 두 기기 비교 (도메인 기준) ────────────────────────────────────

def _domains_for_device(conn, device_id, start, end):
    where, params = ["v.device_id = ?", "v.domain IS NOT NULL"], [int(device_id)]
    if start is not None:
        where.append("v.visit_time >= ?"); params.append(int(start))
    if end is not None:
        where.append("v.visit_time < ?"); params.append(int(end))
    rows = conn.execute(
        "SELECT v.domain, COUNT(*) AS count FROM visits v "
        "WHERE " + " AND ".join(where) + " GROUP BY v.domain", params)
    return {r["domain"]: r["count"] for r in rows}


def compare(conn, device_a, device_b, *, start=None, end=None, limit=100):
    a = _domains_for_device(conn, device_a, start, end)
    b = _domains_for_device(conn, device_b, start, end)
    sa, sb = set(a), set(b)
    both = sorted(sa & sb, key=lambda d: -(a[d] + b[d]))
    only_a = sorted(sa - sb, key=lambda d: -a[d])
    only_b = sorted(sb - sa, key=lambda d: -b[d])

    def pack(domains):
        return [{"domain": d, "count_a": a.get(d, 0), "count_b": b.get(d, 0)}
                for d in domains[:limit]]

    return {
        "device_a": int(device_a), "device_b": int(device_b),
        "both_count": len(both), "only_a_count": len(only_a), "only_b_count": len(only_b),
        "both": pack(both), "only_a": pack(only_a), "only_b": pack(only_b),
    }


# ── 수집(ingest): 원격/모바일 기록을 받아 적재 ───────────────────

def ingest(conn, device_name, os_str, visits):
    device_id = db.get_or_create_device(conn, device_name, os_str or "")
    rows = sorted(visits, key=lambda r: r.get("browser", "unknown"))
    new = 0
    for browser, group in groupby(rows, key=lambda r: r.get("browser", "unknown")):
        new += db.insert_visits(conn, device_id, browser, list(group), source="ingest")
    conn.commit()
    return {"device_id": device_id, "new": new}
