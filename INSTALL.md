# 설치 & 실행 가이드 (데스크탑 · 모바일)

이 앱은 **로컬 우선** 도구다. 브라우저 기록 *수집*은 데스크탑(Windows/macOS/Linux)에서
이뤄지고, *조회*는 데스크탑은 물론 폰에서도 가능하다.

> **솔직한 한계 (먼저 읽어주세요)**
> - 📱 폰의 브라우저 기록을 폰에서 직접 읽는 건 OS가 막아 **불가능**합니다. 모바일은
>   "대시보드를 보는 것" + "Takeout/내보내기 import(M4)"로 처리합니다.
> - 🧱 Windows `.exe` / macOS `.app` / Android `.apk`는 **각 OS에서 빌드**해야 합니다
>   (크로스 빌드·코드서명 불가). 이 저장소엔 빌드 스크립트와 가이드가 들어 있습니다.

---

## 방법 A — 소스로 바로 실행 (가장 간단, 권장)

요구사항: **Python 3.8+** (그 외 설치 불필요 — 표준 라이브러리만 사용)

```bash
# 저장소 내려받기 (또는 GitHub에서 "Download ZIP")
git clone <repo-url> && cd moms-archive

# 데모 데이터로 체험
python tools/seed_demo.py --db ./central.db

# 실행 (브라우저 자동 열림)
./run.sh                 # macOS/Linux
run.bat                  # Windows
#   또는:  python -m server.app --open
```

실제 내 기록 수집:
```bash
python -m collector.collect --db ./central.db --device my-laptop
```

## 방법 B — 단일 실행 파일 (Python 설치 없이 더블클릭)

각 OS에서 한 번 빌드하면, 그 결과물(`dist/bhist`)은 Python 없이 실행된다.

```bash
pip install pyinstaller
pyinstaller bhist.spec
#  → 결과물:  dist/bhist        (Windows: dist\bhist.exe)
./dist/bhist                     # 실행 → 서버 시작 + 브라우저 열림 (DB는 사용자 홈에 생성)
```

| 타깃 | 빌드 위치 | 결과물 | 비고 |
|---|---|---|---|
| Linux | Linux | `dist/bhist` | 이 저장소에서 빌드·실행 검증됨 ✅ |
| Windows | Windows | `dist/bhist.exe` | Windows에서 직접 빌드 필요 |
| macOS | macOS | `dist/bhist` | macOS에서 직접 빌드 필요(서명 권장) |

## 모바일에서 보기 (PWA)

1. PC에서 LAN 접속 허용으로 실행:
   ```bash
   ./run.sh --host 0.0.0.0       # 또는  python -m server.app --host 0.0.0.0
   ```
2. 폰을 **같은 와이파이**에 연결한 뒤 브라우저에서 `http://<PC_IP>:8765` 열기
   - PC_IP 확인: Windows `ipconfig`, macOS/Linux `ipconfig getifaddr en0` / `hostname -I`
3. 브라우저 메뉴 → **홈 화면에 추가** → 앱처럼 사용

**데스크탑**(Chrome/Edge, `localhost`)에서는 주소창의 **설치(⊕)** 아이콘으로 PWA를
완전 설치(독립 창·오프라인 셸)할 수 있다.

> ⚠️ 폰에서 *완전한* PWA(서비스 워커/오프라인)는 보안 컨텍스트(**HTTPS** 또는
> `localhost`)가 필요하다. LAN의 평문 HTTP에선 "홈 화면 바로가기" 수준으로 동작하고
> 화면 조회는 정상이다. HTTPS가 필요하면 리버스 프록시(caddy 등)나 자체 서명 인증서를
> 앞단에 두면 된다.

---

## 보안 / 의존성

- **런타임 의존성 0** (Python 표준 라이브러리). 빌드 도구(PyInstaller·Pillow)만 별도.
- 서버 기본 바인딩은 `127.0.0.1`(이 PC만). 폰 접속이 필요할 때만 `--host 0.0.0.0`.
- 중앙 DB(`*.db`)는 `.gitignore`로 저장소에서 제외. DB 암호화·API 토큰은 **M4** 예정.

## 이 환경에서 검증된 것 / 안 된 것

| 항목 | 상태 |
|---|---|
| Linux 소스 실행 / API / 대시보드 | ✅ 검증 |
| PWA 매니페스트·서비스워커·아이콘 서빙 | ✅ 검증 |
| Linux 단일 실행 파일 빌드 + 실행 | ✅ 검증 |
| Windows/macOS 실행 파일 빌드 | ⛔ 미검증(해당 OS에서 빌드 필요) |
| Android/iOS 에뮬레이터 실행 | ⛔ 미검증(에뮬레이터 부재) — 실제 기기/브라우저로 확인 권장 |
