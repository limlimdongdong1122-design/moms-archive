# 브라우저 방문기록 통합 대시보드

여러 기기 · 여러 브라우저의 방문기록을 **한 곳에 모아** 하나의 대시보드에서
기간별 · 브라우저별 · 기기별로 조회하고, **두 기기를 비교**하며, 중복은 제거한다.
모든 데이터는 **로컬 SQLite**에 저장된다. (민감 정보라 M4에서 암호화 예정)

```
[기기A 수집기]─┐
               ├─→ [중앙 SQLite] ⇄ [API + 대시보드 서버] ⇄ [브라우저(PC·폰)]
[기기B 수집기]─┘
       ↑
  모바일 = Google Takeout/내보내기 파일 import (M4)
```

> **설계 원칙:** 로컬 우선 · 네트워크 종속 최소화. 백엔드는 **Python 표준 라이브러리만**
> 사용하고(런타임 의존성 0), 대시보드는 **빌드가 필요 없는 단일 HTML**(바닐라 JS)이다.
> `python` 하나면 오프라인에서 그대로 돈다.

## 빠른 시작

```bash
python tools/seed_demo.py --db ./central.db   # 데모 데이터(가짜 2기기·4브라우저)
./run.sh                                       # macOS/Linux (브라우저 자동 열림)
run.bat                                        # Windows
#   또는:  python -m server.app --open  →  http://127.0.0.1:8765
```

**설치·배포·모바일(PWA) 안내는 [INSTALL.md](INSTALL.md)** 참고.

## 구성 모듈

| 모듈 | 스택 | 역할 |
|---|---|---|
| `collector/` | Python (표준 라이브러리) | 브라우저 history 복사→읽기→정규화→중앙 DB 적재 |
| `collector/vault.py` | cryptography (opt-in) | 마스터 비번 기반 DB 암호화 볼트(at-rest) |
| `collector/import_takeout.py` | Python | Google Takeout(크롬 기록) 가져오기 |
| `server/` | Python `http.server` | 조회·통계·비교·ingest API + 대시보드/PWA 서빙 (+토큰 인증) |
| `server/static/` | 바닐라 JS + PWA | `index.html` 대시보드, `manifest.webmanifest`, `sw.js`, `icons/` |
| `app_entry.py` · `bhist.spec` | PyInstaller | 단일 실행 파일 빌드(데스크탑) |
| `run.sh` · `run.bat` | 셸/배치 | 더블클릭/한 줄 실행 런처 |
| `tools/` | Python | `seed_demo.py`(데모 데이터), `make_icons.py`(아이콘 생성) |

## 진행 상황

- [x] **M1 — 수집기 + 스키마**: Chrome 계열/Firefox/Safari 추출, 타임스탬프 정규화, 중복 제거
- [x] **M2 — API**: 기간·브라우저·기기 필터 조회 + 두 기기 비교 + 통계 + ingest
- [x] **M3 — 대시보드**: 필터·타임라인·통계·비교 UI (반응형, 폰 브라우저 OK)
- [x] **패키징(부분)**: PWA(모바일/데스크탑 설치) + 데스크탑 런처 + 단일 실행 파일 빌드(Linux 검증)
- [x] **M4 — 보안 + 확장**: 마스터 비번→DB 암호화(볼트), API 토큰, 모바일 Google Takeout import
- [x] **M5 — 배포 자동화**: 태그(`v*`) 푸시 시 3-OS 바이너리를 GitHub Release에 자동 첨부 (코드서명은 인증서 필요 — 선택)

### API 요약

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/devices` · `GET /api/browsers` | 필터용 목록 |
| `GET /api/visits?device=&browser=&start=&end=&q=&limit=&offset=` | 방문기록 조회(페이지네이션) |
| `GET /api/stats?...` | 총계 · 브라우저별 · 기기별 · 날짜별 · 상위 도메인 |
| `GET /api/compare?a=<id>&b=<id>&start=&end=` | 두 기기 도메인 비교 |
| `POST /api/ingest` | `{device, os, visits:[...]}` 원격/모바일 기록 적재 |

`start`/`end`는 Unix epoch 초(UTC).

## 보안 (암호화 · 토큰)

```bash
# 1) 암호화 볼트 생성(마스터 비번)
python -m collector.vault init --vault ./central.db.enc

# 2) 암호화 볼트로 수집 / 실행  (마스터 비번 입력 또는 BHIST_PASSWORD 환경변수)
python -m collector.collect --vault ./central.db.enc --device my-laptop
python -m server.app --vault ./central.db.enc --auth        # --auth: API 토큰 자동 생성

# 3) 모바일(구글 Takeout) 기록 가져오기
python -m collector.import_takeout --vault ./central.db.enc --device my-phone Takeout.zip
```

- 볼트는 **실행 중에만 복호화**되고 종료 시 자동 재암호화된다(평문 작업 파일 삭제).
- `--auth`/`--token`을 쓰면 시작 시 `http://…/?token=…` 주소가 출력되고, **그 토큰이 있어야 데이터 API에 접근**할 수 있다(폰/LAN 노출 시 권장).
- 암호화는 `pip install cryptography` 필요(코어는 의존성 0이며 평문 모드는 그대로 동작).

## 테스트

```bash
python tests/test_collector.py   # 수집기: 추출·타임스탬프·중복제거
python tests/test_server.py      # API·대시보드 서빙·ingest
python tests/test_auth.py        # API 토큰 인증
python tests/test_vault.py       # 암호화 볼트(암복호화·잠금/해제)
python tests/test_takeout.py     # Takeout 가져오기(json·zip)
```

## Vercel 라이브 데모

`vercel.json`이 `server/static`을 웹 루트로 서빙한다. 백엔드(`/api/*`)가 없는 정적 배포에서는
대시보드가 자동으로 **데모 데이터로 폴백**(`server/static/demo.js`)해 동작 화면을 보여준다.
헤더에 `● 데모 모드 (백엔드 미연결)`로 표시되며, **실제 내 기록은 로컬 실행**(`python -m server.app`)에서만 보인다.

> Vercel이 출력 디렉터리를 자동 인식하지 못하면, 프로젝트 설정의 **Output Directory**를
> `server/static`으로 지정하면 된다.

## 데이터 / 프라이버시

- 본인 기기의 본인 데이터만 다루는 **개인용** 도구다.
- 중앙 저장소(`*.db`)·비밀 파일은 `.gitignore`로 저장소에서 제외된다.
- 서버 기본 바인딩은 `127.0.0.1`(이 PC만). 폰 접속이 필요할 때만 `--host 0.0.0.0`.

---

<sub>참고: 저장소 루트의 `App.jsx`·`main.jsx`·`index.css`는 초기 React 플레이스홀더
스캐폴드이며 이 도구는 사용하지 않는다. (대시보드는 `server/static/index.html`)</sub>
