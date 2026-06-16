"""브라우저 방문기록 수집기 패키지.

여러 브라우저(Chrome 계열 / Firefox / Safari)의 로컬 history 데이터베이스에서
방문기록을 읽어 정규화한 뒤, 중앙 SQLite 저장소에 중복 없이 적재한다.
"""

import sys as _sys

try:  # Windows 콘솔(cp1252)에서도 한글/이모지 출력이 깨지지 않도록 UTF-8 강제
    _sys.stdout.reconfigure(encoding="utf-8")
    _sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

__all__ = ["browsers", "db", "collect"]
