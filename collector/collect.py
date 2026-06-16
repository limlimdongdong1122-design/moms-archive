"""수집기 CLI.

사용 예:
    python -m collector.collect --db ./central.db --device my-laptop
    python -m collector.collect --db ./central.db --device my-laptop --browser chrome --browser firefox
"""

from __future__ import annotations

import argparse
import platform
import sys

from . import browsers, db


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="브라우저 방문기록 수집기")
    ap.add_argument("--db", required=True, help="중앙 SQLite 파일 경로")
    ap.add_argument("--device", required=True,
                    help="이 기기의 이름 (예: my-laptop)")
    ap.add_argument("--browser", action="append", dest="browsers",
                    help="특정 브라우저만 수집 (반복 지정 가능: chrome/firefox/safari/edge/brave)")
    args = ap.parse_args(argv)

    conn = db.connect(args.db)
    device_id = db.get_or_create_device(conn, args.device, platform.platform())

    discovered = browsers.discover()
    if not discovered:
        print("발견된 브라우저 history가 없습니다. (브라우저를 설치/사용한 적이 있는지 확인)")
        return 1

    total_read = total_new = 0
    print(f"[{args.device}] 수집 시작 — 발견된 history {len(discovered)}개")
    for name, family, path in discovered:
        if args.browsers and name not in args.browsers:
            continue
        try:
            rows = browsers.EXTRACTORS[family](path)
        except Exception as exc:  # 한 브라우저 실패가 전체를 막지 않도록
            print(f"  ! {name} 읽기 실패: {exc}", file=sys.stderr)
            continue
        new = db.insert_visits(conn, device_id, name, rows)
        total_read += len(rows)
        total_new += new
        print(f"  - {name:8s}: {len(rows):>6}건 읽음 / 신규 {new}건  ({path})")

    conn.commit()
    conn.close()
    print(f"완료 ✅  총 {total_read}건 중 신규 {total_new}건 저장 "
          f"(중복 {total_read - total_new}건 제외)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
