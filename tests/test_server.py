"""server.queries + server.app 통합 테스트.

  1) 조회/필터/검색/기간 필터
  2) 통계 집계 (브라우저·기기·도메인)
  3) 두 기기 비교(도메인 교집합/차집합)
  4) 라이브 HTTP 서버: API JSON + 정적 대시보드 서빙 + ingest(POST)

실행:  python tests/test_server.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import app as appmod  # noqa: E402
from server import queries  # noqa: E402


def seed(conn):
    queries.ingest(conn, "laptop", "macOS", [
        {"browser": "chrome", "url": "https://github.com/", "domain": "github.com",
         "title": "GitHub", "visit_time": 1718000000},
        {"browser": "chrome", "url": "https://news.ycombinator.com/",
         "domain": "news.ycombinator.com", "title": "HN", "visit_time": 1718000100},
        {"browser": "firefox", "url": "https://only-laptop.com/",
         "domain": "only-laptop.com", "title": "L", "visit_time": 1718000200},
    ])
    queries.ingest(conn, "pc", "Windows", [
        {"browser": "edge", "url": "https://github.com/", "domain": "github.com",
         "title": "GitHub", "visit_time": 1718000300},
        {"browser": "edge", "url": "https://only-pc.com/", "domain": "only-pc.com",
         "title": "P", "visit_time": 1718000400},
    ])


def test_queries(conn):
    devs = {d["name"]: d for d in queries.list_devices(conn)}
    assert len(devs) == 2, devs
    assert devs["laptop"]["visits"] == 3 and devs["pc"]["visits"] == 2, devs

    assert queries.query_visits(conn, browsers=["edge"])["total"] == 2
    r = queries.query_visits(conn, q="only-laptop")
    assert r["total"] == 1 and r["items"][0]["domain"] == "only-laptop.com", r
    assert queries.query_visits(conn, start=1718000300)["total"] == 2

    s = queries.stats(conn)
    assert s["total"] == 5, s
    assert any(b["browser"] == "chrome" and b["count"] == 2 for b in s["per_browser"]), s
    assert {d["device"] for d in s["per_device"]} == {"laptop", "pc"}, s
    assert {d["domain"]: d["count"] for d in s["top_domains"]}["github.com"] == 2

    c = queries.compare(conn, devs["laptop"]["id"], devs["pc"]["id"])
    assert c["both_count"] == 1, c            # github.com
    assert c["only_a_count"] == 2, c          # hn, only-laptop
    assert c["only_b_count"] == 1, c          # only-pc
    assert c["both"][0]["domain"] == "github.com", c
    return devs


def test_live_server(dbpath, devs):
    appmod.DB_PATH = dbpath
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), appmod.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def get(p):
        with urllib.request.urlopen(base + p) as r:
            return json.loads(r.read())

    try:
        assert get("/api/health")["ok"] is True
        assert len(get("/api/devices")) == 2
        assert get("/api/visits?browser=edge")["total"] == 2
        assert get("/api/stats")["total"] == 5
        c = get(f"/api/compare?a={devs['laptop']['id']}&b={devs['pc']['id']}")
        assert c["both_count"] == 1, c

        with urllib.request.urlopen(base + "/") as r:
            html = r.read().decode("utf-8")
        assert "<html" in html.lower() and "대시보드" in html, "대시보드 HTML 서빙 실패"

        body = json.dumps({"device": "phone", "os": "iOS", "visits": [
            {"browser": "safari", "url": "https://m.example.com/",
             "domain": "m.example.com", "title": "m", "visit_time": 1718000500}]}).encode()
        req = urllib.request.Request(base + "/api/ingest", data=body,
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req) as r:
            assert json.loads(r.read())["new"] == 1
        assert len(get("/api/devices")) == 3
    finally:
        httpd.shutdown()


def main():
    tmp = tempfile.mkdtemp(prefix="bhist_srv_")
    dbpath = os.path.join(tmp, "central.db")
    conn = queries.open_conn(dbpath)
    seed(conn)
    devs = test_queries(conn)
    conn.close()
    test_live_server(dbpath, devs)
    print("ALL SERVER TESTS PASSED ✅  (queries + 라이브 API + 정적 서빙 + ingest)")


if __name__ == "__main__":
    main()
