"""중앙 저장소 API + 대시보드 서버 (코어는 표준 라이브러리, 암호화는 opt-in).

실행:
    python -m server.app --db ./central.db                 # 평문 DB, 이 PC에서만
    python -m server.app --vault ./central.db.enc          # 암호화 볼트(마스터 비번)
    python -m server.app --host 0.0.0.0 --auth             # 폰 접속 + API 토큰 자동 생성
    python -m server.app --open                            # 브라우저 자동 열기

폰에서 보기: --host 0.0.0.0 으로 띄운 뒤 폰 브라우저에서 http://<이_PC의_IP>:8765
(토큰을 쓰면 시작 시 출력되는 http://...:8765/?token=... 주소로 접속)
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
import signal
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from collector import vault

from . import queries


def _static_dir() -> Path:
    # PyInstaller로 묶이면 임시 추출 폴더(_MEIPASS) 안의 static을 사용한다.
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", ".")) / "static"
    return Path(__file__).with_name("static")


STATIC_DIR = _static_dir()
DB_PATH = os.environ.get("BHIST_DB", "./central.db")
TOKEN = os.environ.get("BHIST_TOKEN")  # 설정되면 /api/* 에 토큰을 요구

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
    server_version = "BrowserHistoryDashboard/0.4"

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

    def _authorized(self) -> bool:
        if not TOKEN:
            return True
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer ") and secrets.compare_digest(auth[7:], TOKEN):
            return True
        token_q = parse_qs(urlparse(self.path).query).get("token")
        if token_q and secrets.compare_digest(token_q[0], TOKEN):
            return True
        for part in self.headers.get("Cookie", "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                if k == "bhist_token" and secrets.compare_digest(v, TOKEN):
                    return True
        return False

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
            return self._serve_static(u.path)  # "/" → index.html, 그 외 정적/아이콘/매니페스트
        if not self._authorized():
            return self._json({"error": "unauthorized"}, status=401)

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
        if not self._authorized():
            return self._json({"error": "unauthorized"}, status=401)
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
    global DB_PATH, TOKEN
    ap = argparse.ArgumentParser(description="브라우저 방문기록 대시보드 서버")
    ap.add_argument("--db", default=DB_PATH, help="평문 중앙 SQLite 경로")
    ap.add_argument("--vault", help="암호화 볼트(.enc). 지정 시 마스터 비번으로 복호화해 사용")
    ap.add_argument("--host", default="127.0.0.1", help="폰 접속을 허용하려면 0.0.0.0")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--open", action="store_true", help="시작 시 브라우저 자동 열기")
    ap.add_argument("--token", help="API 접근 토큰")
    ap.add_argument("--auth", action="store_true", help="토큰이 없으면 자동 생성")
    args = ap.parse_args(argv)

    session = None
    if args.vault:
        if not vault.available():
            raise SystemExit("암호화 기능엔 cryptography 필요:  pip install cryptography")
        password = os.environ.get("BHIST_PASSWORD") or getpass.getpass("마스터 비밀번호: ")
        session = vault.VaultSession(args.vault, password)
        DB_PATH = session.unlock()
    else:
        DB_PATH = args.db

    TOKEN = args.token or os.environ.get("BHIST_TOKEN")
    if args.auth and not TOKEN:
        TOKEN = secrets.token_urlsafe(24)

    queries.open_conn(DB_PATH).close()  # 스키마 보장

    def _graceful(*_):
        raise KeyboardInterrupt
    for _sig in ("SIGINT", "SIGTERM"):
        try:
            signal.signal(getattr(signal, _sig), _graceful)
        except Exception:
            pass

    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    shown_host = "127.0.0.1" if args.host in ("0.0.0.0", "") else args.host
    base = f"http://{shown_host}:{args.port}"
    url = base + (f"/?token={TOKEN}" if TOKEN else "/")
    print(f"대시보드 실행 중 → {url}   (DB: {DB_PATH}{' · 암호화 볼트' if session else ''})")
    if TOKEN:
        print(f"API 토큰: {TOKEN}")
    if args.host == "0.0.0.0":
        tq = f"/?token={TOKEN}" if TOKEN else ""
        print(f"폰에서 같은 와이파이로:  http://<이_PC의_IP>:{args.port}{tq}")
    if args.open:
        _open_browser_later(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        if session:
            session.lock()
            print("볼트 잠금 완료 🔒")


if __name__ == "__main__":
    main()
