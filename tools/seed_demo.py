"""데모 데이터 생성기 — 실제 브라우저 기록 없이 대시보드를 바로 체험.

실행:
    python tools/seed_demo.py --db ./central.db
    python -m server.app --db ./central.db   # 그리고 대시보드 열기
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import queries  # noqa: E402

SITES = [
    ("https://news.ycombinator.com/", "Hacker News", "news.ycombinator.com"),
    ("https://github.com/", "GitHub", "github.com"),
    ("https://www.google.com/search?q=python", "python - Google 검색", "www.google.com"),
    ("https://www.youtube.com/", "YouTube", "www.youtube.com"),
    ("https://en.wikipedia.org/wiki/SQLite", "SQLite - Wikipedia", "en.wikipedia.org"),
    ("https://www.naver.com/", "NAVER", "www.naver.com"),
    ("https://stackoverflow.com/questions/12345", "질문 - Stack Overflow", "stackoverflow.com"),
    ("https://news.naver.com/", "네이버 뉴스", "news.naver.com"),
    ("https://www.reddit.com/", "Reddit", "www.reddit.com"),
    ("https://chat.openai.com/", "ChatGPT", "chat.openai.com"),
    ("https://mail.google.com/", "Gmail", "mail.google.com"),
    ("https://www.notion.so/", "Notion", "www.notion.so"),
]
DEVICES = [("my-laptop", "macOS"), ("work-pc", "Windows")]
BROWSERS = ["chrome", "firefox", "safari", "edge"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="대시보드 체험용 데모 데이터 생성")
    ap.add_argument("--db", default="./central.db")
    ap.add_argument("--count", type=int, default=400, help="기기당 방문 수")
    args = ap.parse_args(argv)

    conn = queries.open_conn(args.db)
    now = int(time.time())
    for device, os_name in DEVICES:
        visits = []
        for _ in range(args.count):
            url, title, domain = random.choice(SITES)
            visits.append({
                "browser": random.choice(BROWSERS),
                "url": url, "title": title, "domain": domain,
                "visit_time": now - random.randint(0, 14 * 86400)
                              - random.randint(0, 86400),
            })
        res = queries.ingest(conn, device, os_name, visits)
        print(f"  {device:9s}: 신규 {res['new']}건")
    conn.close()
    print(f"완료 ✅  서버 실행:  python -m server.app --db {args.db}")


if __name__ == "__main__":
    main()
