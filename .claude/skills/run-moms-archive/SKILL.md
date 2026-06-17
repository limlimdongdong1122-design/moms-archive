---
name: run-moms-archive
description: >-
  Build, run, screenshot, and drive the 브라우저 방문기록 대시보드
  (browser-history dashboard) — a local-first Python web app. Launches the
  server, drives the dashboard UI (timeline / stats / 두 기기 비교 tabs) with
  headless Chromium and captures screenshots, seeds demo data, calls internals
  directly, and runs the collector / vault / Takeout CLIs. Use when asked to
  run, start, launch, serve, screenshot, smoke-test, or drive this app/dashboard.
---

# Run: 브라우저 방문기록 대시보드

A local-first web app: a **Python stdlib HTTP server** (`server/app.py`) serves
a JSON API (`/api/*`) and a no-build dashboard (`server/static/index.html`,
vanilla JS). Data lives in a local SQLite DB; CLIs (`collector`, `vault`,
`import_takeout`) populate it.

The dashboard is **JS-rendered** (it `fetch`es `/api/*` then builds the DOM), so
the agent path drives it with a **headless-Chromium harness**:
[`.claude/skills/run-moms-archive/driver.mjs`](driver.mjs) (puppeteer-core +
`@sparticuz/chromium`). It loads the page, waits for real data, clicks the three
tabs, and writes a screenshot per view.

All paths below are relative to the repo root (the unit dir).

## Prerequisites

- **Python 3.11** and **Node 22** (both present in this container).
- The screenshot driver needs a headless Chromium. **Do not** use
  `apt install chromium` (Ubuntu 24.04 ships only a *snap stub*) or
  `playwright install` (its CDN is blocked by the env's egress allowlist).
  Instead the driver pulls a prebuilt Chromium from npm — install once:

```bash
npm --prefix .claude/skills/run-moms-archive install
```

No extra `apt` libraries were needed in this container
(`ldd /tmp/chromium | grep "not found"` → 0). See Troubleshooting if Chromium
won't start on a barer image.

## Run (agent path) — launch + screenshot the dashboard

```bash
# 1) seed a demo DB and launch the server in the background
python3 tools/seed_demo.py --db /tmp/run_demo.db --count 120
python3 -m server.app --db /tmp/run_demo.db --host 127.0.0.1 --port 8765 >/tmp/run_srv.log 2>&1 &
SRV=$!
curl -s --retry 30 --retry-connrefused --retry-delay 1 http://127.0.0.1:8765/api/health   # -> {"ok": true}

# 2) drive the running dashboard with headless Chromium → screenshots
node .claude/skills/run-moms-archive/driver.mjs --url http://127.0.0.1:8765 --out /tmp/moms-archive-screens

# 3) stop the server
kill $SRV
```

The driver prints what it saw and writes three PNGs to `/tmp/moms-archive-screens`:

```
conn="● 연결됨"  timelineRows=100  meta="총 240건 중 100건 표시"
screenshot: /tmp/moms-archive-screens/01-timeline.png
stats: totalVisits=240  browserBars=4
screenshot: /tmp/moms-archive-screens/02-stats.png
compare: "my-laptop에만 (0)" / "work-pc에만 (0)"
screenshot: /tmp/moms-archive-screens/03-compare.png
DRIVER OK ✅
```

`01-timeline.png` = populated visit table, `02-stats.png` = browser/day/domain
bars, `03-compare.png` = two-device domain comparison. The driver exits
non-zero if the dashboard renders no data (API/DB problem).

Drive any reachable instance by passing a different `--url` (e.g. a Vercel
deploy, which runs in static **demo mode**).

## Direct invocation (internal PRs)

Most non-UI changes touch `server/queries.py` or `collector/*`. Call them
without the browser:

```bash
python3 -c "from server import queries; c=queries.open_conn('/tmp/run_demo.db'); print(queries.stats(c)['total'])"   # -> 240
```

Other entry points (all stdlib, see [INSTALL.md](../../../INSTALL.md)):
`python3 -m collector.collect --db DB --device NAME` (read this machine's
browser history), `python3 -m collector.vault init --vault V.enc` (encrypted
vault), `python3 -m collector.import_takeout --db DB --device NAME Takeout.zip`.

## Run (human path)

`python3 -m server.app --open` starts the server and opens a browser at
`http://127.0.0.1:8765`. Useless headless — use the driver above.

## Test

```bash
python3 tests/test_collector.py
python3 tests/test_server.py
python3 tests/test_auth.py
python3 tests/test_vault.py     # needs: pip install --break-system-packages cryptography
python3 tests/test_takeout.py
```

## Gotchas

- **`apt install chromium` is a trap on Ubuntu 24.04** — `/usr/bin/chromium-browser`
  is a snap stub that prints *"requires the chromium snap to be installed"* and
  never launches. The driver avoids it entirely.
- **Playwright's installer is blocked here** — `playwright install chromium`
  fails with `403 Host not in allowlist: cdn.playwright.dev`. `@sparticuz/chromium`
  works because the npm registry and GitHub release-assets *are* allowlisted.
- **Running as root** → Chromium needs `--no-sandbox` (the driver adds it +
  `chromium.args`). Without it, launch fails.
- **Screenshot timing** — the page renders after async `fetch`es; a naive
  screenshot is blank. The driver waits for `#timeline-body tr` first.
- **Server must be up before the driver**, else the header shows
  `● 서버 연결 안됨`. On a backend-less *static* deploy the dashboard instead
  falls back to bundled demo data and shows `● 데모 모드 (백엔드 미연결)`.
- **Demo compare shows `A에만 (0) / B에만 (0)`** — `seed_demo.py` gives both
  devices the same site pool, so every domain is shared. Real collected data
  differs.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `requires the chromium snap` | Ignore apt chromium; use `node .../driver.mjs` (bundled Chromium). |
| `403 Host not in allowlist: cdn.playwright.dev` | Don't use `playwright install`; the driver uses `@sparticuz/chromium`. |
| Driver throws `타임라인에 데이터가 없음` | Server not running / wrong `--db`. Check `/tmp/run_srv.log` and that `/api/health` returns `{"ok": true}`. |
| Chromium: `error while loading shared libraries` (barer image) | `apt-get install -y libnss3 libnspr4 libatk-bridge2.0-0t64 libgbm1 libasound2t64 libxkbcommon0 libpango-1.0-0`. |
| `ModuleNotFoundError: cryptography` in test_vault | `pip install --break-system-packages cryptography` (optional, vault-only). |
