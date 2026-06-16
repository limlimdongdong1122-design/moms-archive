"""브라우저 방문기록 수집기 패키지.

여러 브라우저(Chrome 계열 / Firefox / Safari)의 로컬 history 데이터베이스에서
방문기록을 읽어 정규화한 뒤, 중앙 SQLite 저장소에 중복 없이 적재한다.
"""

__all__ = ["browsers", "db", "collect"]
