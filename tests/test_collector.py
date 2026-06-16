"""수집기 단위 테스트.

실제 브라우저 없이, Chrome/Firefox history 포맷을 흉내 낸 가짜 SQLite를 만들어
  1) 추출이 되는지
  2) 타임스탬프가 Unix epoch(UTC)로 정확히 변환되는지
  3) 도메인이 뽑히는지
  4) 중앙 DB 적재 + 중복 제거(UNIQUE)가 동작하는지
를 검증한다.

실행:  python tests/test_collector.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector import browsers, db  # noqa: E402

CHROME_OFFSET = 11644473600


def make_chrome(path, rows):
    """rows: [(url, title, unix_ts), ...] → Chrome 포맷 history 생성."""
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE urls(id INTEGER PRIMARY KEY, url TEXT, title TEXT);"
        "CREATE TABLE visits(id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER);"
    )
    for i, (url, title, ts) in enumerate(rows, start=1):
        conn.execute("INSERT INTO urls(id, url, title) VALUES(?,?,?)", (i, url, title))
        chrome_t = int((ts + CHROME_OFFSET) * 1_000_000)
        conn.execute("INSERT INTO visits(url, visit_time) VALUES(?,?)", (i, chrome_t))
    conn.commit()
    conn.close()


def make_firefox(path, rows):
    """rows: [(url, title, unix_ts), ...] → Firefox 포맷 places.sqlite 생성."""
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE moz_places(id INTEGER PRIMARY KEY, url TEXT, title TEXT);"
        "CREATE TABLE moz_historyvisits(id INTEGER PRIMARY KEY, place_id INTEGER, visit_date INTEGER);"
    )
    for i, (url, title, ts) in enumerate(rows, start=1):
        conn.execute("INSERT INTO moz_places(id, url, title) VALUES(?,?,?)", (i, url, title))
        conn.execute("INSERT INTO moz_historyvisits(place_id, visit_date) VALUES(?,?)",
                     (i, int(ts * 1_000_000)))
    conn.commit()
    conn.close()


def main():
    tmp = tempfile.mkdtemp(prefix="bhist_test_")
    chrome_db = os.path.join(tmp, "History")
    firefox_db = os.path.join(tmp, "places.sqlite")
    central = os.path.join(tmp, "central.db")

    make_chrome(chrome_db, [
        ("https://example.com/a", "Example A", 1718000000),
        ("https://news.ycombinator.com/", "Hacker News", 1718000100),
    ])
    make_firefox(firefox_db, [
        ("https://mozilla.org/", "Mozilla", 1718000200),
    ])

    # 1) 추출
    crows = browsers.extract_chromium(chrome_db)
    frows = browsers.extract_firefox(firefox_db)
    assert len(crows) == 2, crows
    assert len(frows) == 1, frows

    # 2) 타임스탬프 정규화 (왕복 일치)
    assert crows[0]["visit_time"] == 1718000000, crows[0]
    assert frows[0]["visit_time"] == 1718000200, frows[0]

    # 3) 도메인 추출
    assert crows[0]["domain"] == "example.com", crows[0]
    assert crows[1]["domain"] == "news.ycombinator.com", crows[1]

    # 4) 적재 + 중복 제거
    conn = db.connect(central)
    dev = db.get_or_create_device(conn, "test-laptop", "TestOS")
    n1 = db.insert_visits(conn, dev, "chrome", crows)
    n2 = db.insert_visits(conn, dev, "firefox", frows)
    assert n1 == 2 and n2 == 1, (n1, n2)

    # 같은 데이터 재적재 → 신규 0건 (중복 제거 확인)
    n3 = db.insert_visits(conn, dev, "chrome", crows)
    assert n3 == 0, n3

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    assert total == 3, total
    conn.close()

    print("ALL TESTS PASSED ✅  (chrome=2, firefox=1, 중복제거 OK, 합계=3)")


if __name__ == "__main__":
    main()
