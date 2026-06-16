"""PyInstaller 단일 실행 파일의 진입점.

빌드:   pyinstaller bhist.spec        →  dist/bhist (Windows는 dist/bhist.exe)
실행:   ./dist/bhist                  →  서버 시작 + 브라우저 자동 열기

더블클릭 실행을 고려해, 인자가 없으면 사용자 홈에 DB를 두고 브라우저를 연다.
"""

import sys
from pathlib import Path

from server.app import main

if __name__ == "__main__":
    argv = sys.argv[1:]
    if not any(a == "--db" or a.startswith("--db=") for a in argv):
        argv += ["--db", str(Path.home() / "browser-history.db")]
    if "--open" not in argv:
        argv += ["--open"]
    main(argv)
