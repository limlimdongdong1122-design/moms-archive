"""브라우저별 history 데이터베이스 탐지 및 추출.

설계 메모
---------
* history 파일은 브라우저 실행 중 잠겨 있을 수 있으므로 임시 폴더로 복사한 뒤
  읽기 전용으로 연다. (WAL/SHM 사이드카도 함께 복사)
* 브라우저마다 타임스탬프 기준(epoch)이 달라 모두 Unix epoch 초(UTC)로 정규화한다.
    - Chrome 계열 : 1601-01-01 기준 마이크로초
    - Firefox     : 1970-01-01 기준 마이크로초
    - Safari      : 2001-01-01 기준 초 (Cocoa Core Data)
"""

from __future__ import annotations

import glob
import os
import platform
import shutil
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import urlparse

# epoch 보정값(초)
CHROME_EPOCH_OFFSET = 11644473600  # 1601-01-01 → 1970-01-01
COCOA_EPOCH_OFFSET = 978307200     # 1970-01-01 → 2001-01-01


def domain_of(url: str):
    """URL에서 도메인(netloc)을 추출. 실패하면 None."""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc or None
    except Exception:
        return None


def _norm(url, title, unix_ts) -> dict:
    return {
        "url": url,
        "title": title,
        "domain": domain_of(url),
        "visit_time": int(unix_ts),
    }


def _read_sqlite(path: str, query: str) -> list[dict]:
    """잠김을 피하려 복사본을 만든 뒤 읽기 전용으로 쿼리한다."""
    tmpdir = tempfile.mkdtemp(prefix="bhist_")
    try:
        dst = Path(tmpdir) / Path(path).name
        shutil.copy2(path, dst)
        # WAL/SHM 사이드카도 있으면 같이 복사 (최근 기록 누락 방지)
        for suffix in ("-wal", "-shm"):
            side = Path(str(path) + suffix)
            if side.exists():
                shutil.copy2(side, Path(tmpdir) / side.name)

        conn = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
        try:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(query)]
        finally:
            conn.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ── 브라우저별 추출기 ─────────────────────────────────────────────

def extract_chromium(path: str) -> list[dict]:
    rows = _read_sqlite(
        path,
        "SELECT urls.url AS url, urls.title AS title, visits.visit_time AS t "
        "FROM visits JOIN urls ON visits.url = urls.id",
    )
    out = []
    for r in rows:
        if not r["t"]:
            continue
        ts = int(r["t"]) / 1_000_000 - CHROME_EPOCH_OFFSET
        if ts <= 0:
            continue
        out.append(_norm(r["url"], r["title"], ts))
    return out


def extract_firefox(path: str) -> list[dict]:
    rows = _read_sqlite(
        path,
        "SELECT p.url AS url, p.title AS title, h.visit_date AS t "
        "FROM moz_historyvisits h JOIN moz_places p ON h.place_id = p.id",
    )
    out = []
    for r in rows:
        if not r["t"]:
            continue
        ts = int(r["t"]) / 1_000_000
        out.append(_norm(r["url"], r["title"], ts))
    return out


def extract_safari(path: str) -> list[dict]:
    rows = _read_sqlite(
        path,
        "SELECT i.url AS url, v.title AS title, v.visit_time AS t "
        "FROM history_visits v JOIN history_items i ON v.history_item = i.id",
    )
    out = []
    for r in rows:
        if r["t"] is None:
            continue
        ts = float(r["t"]) + COCOA_EPOCH_OFFSET
        out.append(_norm(r["url"], r["title"], ts))
    return out


EXTRACTORS = {
    "chromium": extract_chromium,
    "firefox": extract_firefox,
    "safari": extract_safari,
}


# ── history 파일 탐지 ─────────────────────────────────────────────

def _candidates(system: str):
    """(브라우저이름, 추출기family, [glob 패턴...]) 목록을 OS별로 반환."""
    home = Path.home()
    out = []

    if system == "Linux":
        chromium_bases = {
            "chrome": home / ".config/google-chrome",
            "chromium": home / ".config/chromium",
            "edge": home / ".config/microsoft-edge",
            "brave": home / ".config/BraveSoftware/Brave-Browser",
        }
        for name, base in chromium_bases.items():
            out.append((name, "chromium",
                        [base / "Default/History", base / "Profile */History"]))
        out.append(("firefox", "firefox",
                    [home / ".mozilla/firefox/*/places.sqlite"]))

    elif system == "Darwin":  # macOS
        appsup = home / "Library/Application Support"
        chromium_bases = {
            "chrome": appsup / "Google/Chrome",
            "edge": appsup / "Microsoft Edge",
            "brave": appsup / "BraveSoftware/Brave-Browser",
            "chromium": appsup / "Chromium",
        }
        for name, base in chromium_bases.items():
            out.append((name, "chromium",
                        [base / "Default/History", base / "Profile */History"]))
        out.append(("firefox", "firefox",
                    [appsup / "Firefox/Profiles/*/places.sqlite"]))
        out.append(("safari", "safari",
                    [home / "Library/Safari/History.db"]))

    elif system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData/Local"))
        roaming = Path(os.environ.get("APPDATA", home / "AppData/Roaming"))
        chromium_bases = {
            "chrome": local / "Google/Chrome/User Data",
            "edge": local / "Microsoft/Edge/User Data",
            "brave": local / "BraveSoftware/Brave-Browser/User Data",
            "chromium": local / "Chromium/User Data",
        }
        for name, base in chromium_bases.items():
            out.append((name, "chromium",
                        [base / "Default/History", base / "Profile */History"]))
        out.append(("firefox", "firefox",
                    [roaming / "Mozilla/Firefox/Profiles/*/places.sqlite"]))

    return out


def discover(system: str | None = None):
    """현재 OS에서 발견된 (브라우저이름, family, 파일경로) 목록."""
    system = system or platform.system()
    found = []
    for name, family, patterns in _candidates(system):
        for pat in patterns:
            for p in glob.glob(str(pat)):
                if os.path.isfile(p):
                    found.append((name, family, p))
    return found
