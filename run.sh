#!/usr/bin/env bash
# 데스크탑 실행 (Python 3.8+ 필요). 서버를 띄우고 브라우저를 엽니다.
# 폰에서도 보려면:  ./run.sh --host 0.0.0.0
cd "$(dirname "$0")" || exit 1
exec python3 -m server.app --open "$@"
