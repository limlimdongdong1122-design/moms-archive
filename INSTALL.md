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

## 릴리스(배포) 만들기

태그를 푸시하면 CI가 3-OS 바이너리를 빌드해 GitHub Release에 자동 첨부한다.

```bash
git tag v0.1.0
git push origin v0.1.0
# → Actions(build-desktop) 실행 후 v0.1.0 릴리스에
#   bhist-Linux-x64 / bhist-macOS-x64 / bhist-Windows-x64.exe 가 첨부됨
```

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

## 보안: 암호화 볼트 · API 토큰

민감 정보라, 중앙 DB를 마스터 비밀번호로 암호화할 수 있다. (`pip install cryptography` 필요)

```bash
python -m collector.vault init --vault ./central.db.enc          # 볼트 생성
python -m collector.collect --vault ./central.db.enc --device my-laptop
python -m server.app --vault ./central.db.enc --auth             # 토큰 자동 생성
```

- 볼트는 **실행 중에만 복호화**되고, 종료 시 자동 재암호화 + 평문 작업 파일 삭제.
- 비밀번호는 프롬프트 입력 또는 `BHIST_PASSWORD` 환경변수.
- `--auth`(자동) 또는 `--token <값>`으로 API 토큰을 켜면, 시작 시 출력되는
  `http://…:8765/?token=…` 주소로 접속해야 데이터가 보인다. **폰/LAN 노출 시 꼭 사용 권장.**

## 모바일 기록 가져오기 (Google Takeout)

폰의 크롬 기록은 OS가 막아 직접 못 읽으므로, [Google Takeout](https://takeout.google.com)에서
Chrome 데이터를 내보낸 뒤 가져온다.

```bash
python -m collector.import_takeout --db ./central.db --device my-phone Takeout.zip
#   History.json 직접:  ... --device my-phone History.json
#   암호화 볼트로:       ... --vault ./central.db.enc --device my-phone Takeout.zip
```

## 보안 / 의존성

- **코어 런타임 의존성 0** (Python 표준 라이브러리). 암호화만 `cryptography`(선택).
- 서버 기본 바인딩은 `127.0.0.1`(이 PC만). 폰 접속이 필요할 때만 `--host 0.0.0.0` + 토큰.
- 중앙 DB(`*.db`)·볼트(`*.enc`)는 `.gitignore`로 저장소에서 제외.

## 이 환경에서 검증된 것 / 안 된 것

| 항목 | 상태 |
|---|---|
| Linux 소스 실행 / API / 대시보드 | ✅ 검증 |
| PWA 매니페스트·서비스워커·아이콘 서빙 | ✅ 검증 |
| Linux 단일 실행 파일 빌드 + 실행 | ✅ 검증 |
| 암호화 볼트 + API 토큰(생성·인증·잠금·재시작 데이터 유지) | ✅ 검증 |
| Takeout 가져오기(json·zip) | ✅ 검증 |
| Windows/macOS 실행 파일 빌드 | ⛔ 미검증(해당 OS에서 빌드 필요) |
| Android/iOS 에뮬레이터 실행 | ⛔ 미검증(에뮬레이터 부재) — 실제 기기/브라우저로 확인 권장 |
