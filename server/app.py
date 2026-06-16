"""중앙 저장소 API + 대시보드 서버 (표준 라이브러리만).

실행:
    python -m server.app --db ./central.db                 # 이 PC에서만
    python -m server.app --db ./central.db --host 0.0.0.0  # 폰 등 같은 와이파이에서 접속

폰에서 보기: 서버를 --host 0.0.0.0 으로 띄운 뒤 폰 브라우저에서
    http://<이_PC의_IP>:8765
"""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from . import queries

STATIC_DIR = Path(__file__).with_name("static")
DB_PATH = os.environ.get("BHIST_DB", "./central.db")


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
    server_version = "BrowserHistoryDashboard/0.2"

    def log_message(self, *_):  # 요청 로그 조용히
        pass

    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _static(self, name="index.html"):
        path = STATIC_DIR / name
        if not path.is_file():
            self.send_error(404, "not found")
            return
        body = path.read_bytes()
        ctype = "text/html; charset=utf-8" if name.endswith(".html") else "application/octet-stream"
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
        if u.path in ("/", "/index.html"):
            return self._static("index.html")
        if not u.path.startswith("/api/"):
            return self.send_error(404, "not found")

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
        except Exception as exc:  # 잘못된 파라미터 등
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


def main(argv=None):
    global DB_PATH
    ap = argparse.ArgumentParser(description="브라우저 방문기록 대시보드 서버")
    ap.add_argument("--db", default=DB_PATH, help="중앙 SQLite 경로")
    ap.add_argument("--host", default="127.0.0.1", help="폰 접속을 허용하려면 0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    DB_PATH = args.db
    queries.open_conn(DB_PATH).close()  # 스키마 보장

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"대시보드 실행 중 → http://{args.host}:{args.port}   (DB: {DB_PATH})")
    if args.host == "0.0.0.0":
        print(f"폰에서 같은 와이파이로:  http://<이_PC의_IP>:{args.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")


if __name__ == "__main__":
    main()
