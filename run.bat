@echo off
REM 데스크탑 실행 (Python 3.8+ 필요). 서버를 띄우고 브라우저를 엽니다.
REM 폰에서도 보려면:  run.bat --host 0.0.0.0
cd /d "%~dp0"
python -m server.app --open %*
