"""중앙 저장소 API + 대시보드 서버 (표준 라이브러리만).

실행:
    python -m server.app --db ./central.db                 # 이 PC에서만
    python -m server.app --db ./central.db --host 0.0.0.0  # 폰 등 같은 와이파이에서 접속
    python -m server.app --open                            # 브라우저 자동 열기

폰에서 보기: 서버를 --host 0.0.0.0 으로 띄운 뒤 폰 브라우저에서
    http://<이_PC의_IP>:8765
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import queries


def _static_dir() -> Path:
    # PyInstaller로 묶이면 임시 추출 폴더(_MEIPASS) 안의 static을 사용한다.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", ".")) / "static"
    return Path(__file__).with_name("static")


STATIC_DIR = _static_dir()
DB_PATH = os.environ.get("BHIST_DB", "./central.db")

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webmanifest": "application/manifest+json; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def _ints(values):
    out = []
    for v in values:
        out += [int(p) for p in v.split(",") if p.strip()]
    return out


def _strs(values):
    out = []
    for v in values:
        out += [p.strip() for p in v.split(",") if p.strip()]
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "BrowserHistoryDashboard/0.3"

    def log_message(self, *_):  # 요청 로그 조용히
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, relpath):
        relpath = relpath.lstrip("/") or "index.html"
        base = STATIC_DIR.resolve()
        target = (base / relpath).resolve()
        if base != target and base not in target.parents:  # 디렉터리 탈출 방지
            return self.send_error(404, "not found")
        if not target.is_file():
            return self.send_error(404, "not found")
        body = target.read_bytes()
        ctype = CONTENT_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _filters(self, qs):
        return dict(
            device_ids=_ints(qs.get("device", [])) or None,
            browsers=_strs(qs.get("browser", [])) or None,
            start=int(qs["start"][0]) if qs.get("start") else None,
            end=int(qs["end"][0]) if qs.get("end") else None,
            q=qs["q"][0] if qs.get("q") else None,
        )

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        if not u.path.startswith("/api/"):
            return self._serve_static(u.path)  # "/" → index.html, 그 외 정적 파일/아이콘/매니페스트

        conn = queries.open_conn(DB_PATH)
        try:
            if u.path == "/api/health":
                return self._json({"ok": True})
            if u.path == "/api/devices":
                return self._json(queries.list_devices(conn))
            if u.path == "/api/browsers":
                return self._json(queries.list_browsers(conn))
            if u.path == "/api/visits":
                f = self._filters(qs)
                limit = int(qs.get("limit", ["200"])[0])
                offset = int(qs.get("offset", ["0"])[0])
                return self._json(queries.query_visits(conn, limit=limit, offset=offset, **f))
            if u.path == "/api/stats":
                return self._json(queries.stats(conn, **self._filters(qs)))
            if u.path == "/api/compare":
                f = self._filters(qs)
                return self._json(queries.compare(
                    conn, int(qs["a"][0]), int(qs["b"][0]),
                    start=f["start"], end=f["end"]))
            return self.send_error(404, "unknown endpoint")
        except Exception as exc:
            return self._json({"error": str(exc)}, status=400)
        finally:
            conn.close()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/ingest":
            return self.send_error(404, "not found")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
            conn = queries.open_conn(DB_PATH)
            try:
                res = queries.ingest(conn, payload["device"],
                                     payload.get("os", ""), payload.get("visits", []))
            finally:
                conn.close()
            return self._json(res)
        except Exception as exc:
            return self._json({"error": str(exc)}, status=400)


def _open_browser_later(url):
    def _open():
        try:
            webbrowser.open(url)
        except Exception:
            pass
    threading.Timer(0.8, _open).start()


def main(argv=None):
    global DB_PATH
    ap = argparse.ArgumentParser(description="브라우저 방문기록 대시보드 서버")
    ap.add_argument("--db", default=DB_PATH, help="중앙 SQLite 경로")
    ap.add_argument("--host", default="127.0.0.1", help="폰 접속을 허용하려면 0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="시작 시 브라우저 자동 열기")
    args = ap.parse_args(argv)

    DB_PATH = args.db
    queries.open_conn(DB_PATH).close()  # 스키마 보장

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    shown_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    url = f"http://{shown_host}:{args.port}"
    print(f"대시보드 실행 중 → {url}   (DB: {DB_PATH})")
    if args.host == "0.0.0.0":
        print(f"폰에서 같은 와이파이로:  http://<이_PC의_IP>:{args.port}")
    if args.open:
        _open_browser_later(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
