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

> **설계 원칙:** 로컬 우선 · 네트워크 종속 최소화. 그래서 백엔드는 **Python 표준
> 라이브러리만** 사용하고(별도 설치 불필요), 대시보드는 **빌드가 필요 없는 단일
> HTML**(바닐라 JS)로 만들었다. `python` 하나면 오프라인에서 그대로 돈다.

> **모바일 안내:** iOS 사파리·안드로이드 크롬은 OS가 history 파일 접근을 막아둬서
> PC처럼 직접 읽을 수 없다. 모바일 **기록**은 Google Takeout/내보내기 import로 합치고
> (M4), 대시보드 **화면**은 서버를 `--host 0.0.0.0`으로 띄워 폰 브라우저로 본다.

## 구성 모듈

| 모듈 | 스택 | 역할 |
|---|---|---|
| `collector/` | Python (표준 라이브러리) | 브라우저 history 복사→읽기→정규화→중앙 DB 적재 |
| `server/` | Python `http.server` | 조회·통계·비교·수집(ingest) API + 대시보드 서빙 |
| `server/static/index.html` | 바닐라 JS (빌드 없음) | 타임라인·통계·두 기기 비교 UI (반응형) |
| `tools/seed_demo.py` | Python | 체험용 데모 데이터 생성 |

## 진행 상황

- [x] **M1 — 수집기 + 스키마**: Chrome 계열/Firefox/Safari 추출, 타임스탬프 정규화, 중복 제거
- [x] **M2 — API**: 기간·브라우저·기기 필터 조회 + 두 기기 비교 + 통계 + ingest
- [x] **M3 — 대시보드**: 필터·타임라인·통계·비교 UI (폰 브라우저 OK)
- [ ] **M4 — 보안 + 확장**: 마스터 비번→암호화, API 토큰 / 모바일 Takeout import
- [ ] **M5 — 패키징**: 실행 스크립트 + 배포 문서

## 빠른 시작 (데모 데이터로 바로 체험)

설치할 것 없이 Python 3 만 있으면 된다.

```bash
# 1) 데모 데이터 생성 (가짜 2기기 · 4브라우저)
python tools/seed_demo.py --db ./central.db

# 2) 서버 실행
python -m server.app --db ./central.db

# 3) 브라우저에서 http://127.0.0.1:8765 열기
```

## 실제 사용

```bash
# 각 기기에서 본인 브라우저 기록 수집 (--device 이름만 다르게)
python -m collector.collect --db ./central.db --device my-laptop
python -m collector.collect --db ./central.db --device work-pc

# 대시보드 실행 (폰에서도 보려면 0.0.0.0)
python -m server.app --db ./central.db --host 0.0.0.0
#  → 폰 브라우저에서 http://<이_PC의_IP>:8765
```

여러 기기의 `central.db`를 한곳에 모으거나, 다른 기기에서 `POST /api/ingest`로
보내면 기록이 합쳐진다. 같은 (기기·브라우저·URL·시각) 기록은 자동 중복 제거된다.

### API 요약

| 엔드포인트 | 설명 |
|---|---|
| `GET /api/devices` · `GET /api/browsers` | 필터용 목록 |
| `GET /api/visits?device=&browser=&start=&end=&q=&limit=&offset=` | 방문기록 조회(페이지네이션) |
| `GET /api/stats?...` | 총계 · 브라우저별 · 기기별 · 날짜별 · 상위 도메인 |
| `GET /api/compare?a=<id>&b=<id>&start=&end=` | 두 기기 도메인 비교(양쪽/각각만) |
| `POST /api/ingest` | `{device, os, visits:[...]}` 원격/모바일 기록 적재 |

`start`/`end`는 Unix epoch 초(UTC).

## 테스트

```bash
python tests/test_collector.py   # 수집기: 추출·타임스탬프·중복제거
python tests/test_server.py      # API·대시보드 서빙·ingest
```

## 데이터 / 프라이버시

- 본인 기기의 본인 데이터만 다루는 **개인용** 도구다.
- 중앙 저장소(`*.db`)·비밀 파일은 `.gitignore`로 저장소에서 제외된다.
- 서버 기본 바인딩은 `127.0.0.1`(이 PC만). 폰 접속이 필요할 때만 `--host 0.0.0.0`.
- M4에서 마스터 비밀번호 기반 암호화와 API 토큰을 추가한다.

---

<sub>참고: 저장소 루트의 `App.jsx`·`main.jsx`·`index.css`는 초기 React 플레이스홀더
스캐폴드이며 이 도구는 사용하지 않는다. (대시보드는 `server/static/index.html`)</sub>
