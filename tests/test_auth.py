"""API 토큰 인증 테스트.  실행: python tests/test_auth.py"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from server import app as appmod  # noqa: E402
from server import queries  # noqa: E402

TOKEN = "secret-token-123"


def main():
    tmp = tempfile.mkdtemp(prefix="bhist_auth_")
    dbp = os.path.join(tmp, "c.db")
    queries.open_conn(dbp).close()
    appmod.DB_PATH = dbp
    appmod.TOKEN = TOKEN

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), appmod.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    def expect_401(req):
        try:
            urllib.request.urlopen(req)
            raise AssertionError("401이어야 하는데 통과됨")
        except urllib.error.HTTPError as e:
            assert e.code == 401, e.code

    try:
        # 토큰 없음 → 401
        expect_401(base + "/api/health")
        # 틀린 토큰 → 401
        expect_401(urllib.request.Request(base + "/api/health",
                                          headers={"Authorization": "Bearer wrong"}))
        # 헤더 토큰 → 200
        req = urllib.request.Request(base + "/api/health",
                                     headers={"Authorization": "Bearer " + TOKEN})
        assert json.loads(urllib.request.urlopen(req).read())["ok"] is True
        # 쿼리 토큰 → 200
        q = urllib.parse.urlencode({"token": TOKEN})
        assert json.loads(urllib.request.urlopen(f"{base}/api/health?{q}").read())["ok"] is True
        # 쿠키 토큰 → 200
        req = urllib.request.Request(base + "/api/health",
                                     headers={"Cookie": "bhist_token=" + TOKEN})
        assert json.loads(urllib.request.urlopen(req).read())["ok"] is True
        # 정적 파일은 토큰 없이 허용
        assert urllib.request.urlopen(base + "/manifest.webmanifest").status == 200
        assert urllib.request.urlopen(base + "/").status == 200
    finally:
        httpd.shutdown()
        appmod.TOKEN = None  # 다른 테스트에 영향 없도록 복구

    print("AUTH TESTS PASSED ✅  (401·헤더·쿼리·쿠키·정적허용)")


if __name__ == "__main__":
    main()
