"""Google Takeout(크롬 방문기록) 가져오기 — 모바일 기록 합치기용.

폰의 크롬 방문기록은 OS가 직접 접근을 막으므로, Google Takeout으로 내보낸
`History.json`(또는 Takeout zip)을 가져와 중앙 DB에 합친다.

사용:
    python -m collector.import_takeout --db ./central.db --device my-phone Takeout.zip
    python -m collector.import_takeout --db ./central.db --device my-phone History.json
"""

from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from . import db, vault


def _domain(url):
    try:
        return urlparse(url).netloc.lower() or None
    except Exception:
        return None


def _parse_history_json(text: str):
    data = json.loads(text)
    if isinstance(data, dict):
        items = data.get("Browser History") or data.get("visits") or []
    else:
        items = data or []
    rows = []
    for it in items:
        url = it.get("url")
        if not url:
            continue
        t = it.get("time_usec", it.get("visit_time", it.get("time")))
        if t is None:
            continue
        t = int(t)
        # time_usec(마이크로초)면 초로 변환, 이미 초면 그대로
        visit_time = t // 1_000_000 if t > 10_000_000_000 else t
        rows.append({
            "url": url,
            "title": it.get("title"),
            "domain": _domain(url),
            "visit_time": visit_time,
        })
    return rows


def _load(src_path: str):
    p = Path(src_path)
    if p.suffix.lower() == ".zip" or zipfile.is_zipfile(str(p)):
        with zipfile.ZipFile(str(p)) as z:
            names = [n for n in z.namelist() if n.lower().endswith("history.json")]
            names.sort(key=lambda n: ("chrome" not in n.lower(), len(n)))  # Chrome 우선
            if not names:
                raise SystemExit("zip 안에서 History.json 을 찾지 못했습니다.")
            rows = []
            for n in names:
                rows += _parse_history_json(z.read(n).decode("utf-8", "replace"))
            return rows
    return _parse_history_json(p.read_text(encoding="utf-8", errors="replace"))


def run(db_path: str, device: str, src_path: str, browser: str = "chrome") -> int:
    rows = _load(src_path)
    conn = db.connect(db_path)
    try:
        device_id = db.get_or_create_device(conn, device, "takeout")
        new = db.insert_visits(conn, device_id, browser, rows, source="takeout")
        conn.commit()
    finally:
        conn.close()
    return new


def main(argv=None):
    ap = argparse.ArgumentParser(description="Google Takeout 방문기록 가져오기")
    target = ap.add_mutually_exclusive_group(required=True)
    target.add_argument("--db", help="평문 중앙 SQLite 경로")
    target.add_argument("--vault", help="암호화 볼트(.enc)")
    ap.add_argument("--device", required=True, help="기기 이름 (예: my-phone)")
    ap.add_argument("src", help="Takeout zip 또는 History.json 경로")
    args = ap.parse_args(argv)

    db_path, session = vault.open_db(args.db, args.vault)
    try:
        new = run(db_path, args.device, args.src)
        print(f"가져오기 완료 ✅  신규 {new}건 적재 ({args.device})")
    finally:
        if session:
            session.lock()
            print("볼트 잠금 완료 🔒")


if __name__ == "__main__":
    main()
