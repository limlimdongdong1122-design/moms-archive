"""중앙 저장소 API + 대시보드 서버 패키지.

표준 라이브러리만으로 동작하는 작은 HTTP 서버가
  * 방문기록 조회 / 통계 / 두 기기 비교 / 수집(ingest) API
  * 정적 대시보드(index.html)
를 함께 제공한다.
"""

import sys as _sys

try:  # Windows 콘솔(cp1252)에서도 한글/이모지 출력이 깨지지 않도록 UTF-8 강제
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

__all__ = ["queries", "app"]
