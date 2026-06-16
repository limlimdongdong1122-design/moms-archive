# 브라우저 방문기록 통합 대시보드

여러 기기 · 여러 브라우저의 방문기록을 **한 곳에 모아** 하나의 대시보드에서
기간별 · 브라우저별 · 기기별로 조회하고, **두 기기를 비교**하며, 중복은 제거한다.
모든 데이터는 **로컬에 저장**(SQLite)되고, 민감 정보라 암호화를 적용한다.

```
[기기A 수집기]─┐
               ├─→ [중앙 SQLite (암호화)] ⇄ [API: FastAPI] ⇄ [대시보드: React]
[기기B 수집기]─┘                                              (PC·폰 브라우저로 접속)
       ↑
  모바일 = Google Takeout/내보내기 파일 import
```

> **모바일 안내:** iOS 사파리·안드로이드 크롬은 OS가 history 파일 접근을 막아둬서
> PC처럼 직접 읽을 수 없다. 모바일 기록은 **Google Takeout / 브라우저 내보내기**
> 파일을 import 하는 방식으로 합치고, 대시보드는 폰 브라우저로 접속해 본다.

## 구성 모듈

| 모듈 | 스택 | 역할 |
|---|---|---|
| `collector/` | Python (표준 라이브러리만) | 브라우저 history 복사→읽기→정규화→중앙 DB 적재 |
| `server/` | FastAPI *(예정)* | 조회·비교·통계·수집 API |
| `dashboard/` | React + Vite + Tailwind *(예정)* | 타임라인·필터·비교·통계 UI |

## 진행 상황

- [x] **M1 — 수집기 + 스키마**: Chrome 계열/Firefox/Safari 추출, 타임스탬프 정규화, 중복 제거
- [ ] **M2 — API**: 기간·브라우저·기기 필터 조회 + 두 기기 비교 + 통계 + ingest
- [ ] **M3 — 대시보드**: 필터·타임라인·비교·통계 (반응형)
- [ ] **M4 — 보안 + 확장**: 마스터 비번→암호화, API 토큰 / 모바일 Takeout import
- [ ] **M5 — 패키징**: 실행 스크립트 + 문서

## 수집기 사용법 (M1)

별도 설치 없이 Python 3 표준 라이브러리만으로 동작한다.

```bash
# 이 기기의 브라우저 기록을 중앙 DB(central.db)로 수집
python -m collector.collect --db ./central.db --device my-laptop

# 특정 브라우저만
python -m collector.collect --db ./central.db --device my-laptop --browser chrome --browser firefox
```

다른 기기에서도 같은 명령을 `--device` 이름만 바꿔 실행한 뒤, 생성된
`central.db`를 한곳으로 모으면 두 기기의 기록이 합쳐진다.
(M2 API가 붙으면 네트워크로 바로 모으는 방식도 추가된다.)

지원 브라우저: **Chrome · Edge · Brave · Chromium · Firefox**(전 OS), **Safari**(macOS).
탐지 위치는 Linux/macOS/Windows를 자동 판별한다.

## 테스트

```bash
python tests/test_collector.py
```

가짜 history DB로 추출·타임스탬프 변환·중복 제거를 검증한다.

## 데이터 / 프라이버시

- 방문기록은 **본인 기기의 본인 데이터**만 수집하는 개인용 도구다.
- 중앙 저장소(`*.db`)와 비밀 파일은 `.gitignore`로 저장소에서 제외된다.
- 민감 정보이므로 M4에서 마스터 비밀번호 기반 암호화와 로컬 바인딩을 적용한다.
