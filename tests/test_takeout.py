"""Takeout 가져오기 단위 테스트.  실행: python tests/test_takeout.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector import db, import_takeout  # noqa: E402

HIST = {"Browser History": [
    {"title": "A", "url": "https://a.com/", "time_usec": 1718000000000000},
    {"title": "B", "url": "https://b.com/x", "time_usec": 1718000100000000},
    {"title": "no-url"},  # url 없으면 무시
]}


def main():
    tmp = tempfile.mkdtemp(prefix="bhist_takeout_")

    # 1) History.json 직접
    jp = os.path.join(tmp, "History.json")
    Path(jp).write_text(json.dumps(HIST), encoding="utf-8")
    dbp = os.path.join(tmp, "c.db")
    n = import_takeout.run(dbp, "my-phone", jp)
    assert n == 2, n

    conn = db.connect(dbp)
    rows = conn.execute(
        "SELECT url, domain, visit_time, source, browser FROM visits ORDER BY visit_time").fetchall()
    conn.close()
    assert rows[0][0] == "https://a.com/" and rows[0][1] == "a.com", rows
    assert rows[0][2] == 1718000000, rows           # time_usec → 초 변환
    assert rows[0][3] == "takeout" and rows[0][4] == "chrome", rows

    # 2) Takeout zip
    zp = os.path.join(tmp, "takeout.zip")
    with zipfile.ZipFile(zp, "w") as z:
        z.writestr("Takeout/Chrome/History.json", json.dumps(HIST))
    dbp2 = os.path.join(tmp, "c2.db")
    assert import_takeout.run(dbp2, "my-phone", zp) == 2

    # 3) 같은 파일 재가져오기 → 중복 제거(신규 0)
    assert import_takeout.run(dbp, "my-phone", jp) == 0

    print("TAKEOUT TESTS PASSED ✅  (json/zip/시각변환/중복제거)")


if __name__ == "__main__":
    main()
