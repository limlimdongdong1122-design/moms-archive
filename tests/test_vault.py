"""볼트(암호화) 단위 테스트.  실행: python tests/test_vault.py"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from collector import db, vault  # noqa: E402


def main():
    if not vault.available():
        print("SKIP: cryptography 미설치")
        return

    tmp = tempfile.mkdtemp(prefix="bhist_vault_")
    vpath = os.path.join(tmp, "central.db.enc")
    work = os.path.join(tmp, "work.db")
    pw = "s3cret-비밀번호!"

    # 새 볼트 → 데이터 적재 → 잠금
    sess = vault.VaultSession(vpath, pw, work_path=work)
    wp = sess.unlock()
    conn = db.connect(wp)
    dev = db.get_or_create_device(conn, "laptop", "Linux")
    db.insert_visits(conn, dev, "chrome", [
        {"url": "https://x.com/", "domain": "x.com", "title": "x", "visit_time": 1718000000}])
    conn.commit()
    conn.close()
    sess.lock()
    assert os.path.exists(vpath), "볼트가 생성되지 않음"
    assert not os.path.exists(work), "평문 작업 파일이 삭제되지 않음"

    # 다시 열기 → 데이터 유지 확인
    sess2 = vault.VaultSession(vpath, pw, work_path=work)
    conn = db.connect(sess2.unlock())
    n = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
    conn.close()
    sess2.lock()
    assert n == 1, n

    # 틀린 비밀번호는 실패
    try:
        vault.VaultSession(vpath, "wrong-pw", work_path=work).unlock()
        assert False, "틀린 비밀번호인데 열림"
    except ValueError:
        pass
    assert vault.verify_password(vpath, pw) is True
    assert vault.verify_password(vpath, "nope") is False

    # 직접 암복호화 라운드트립
    src = os.path.join(tmp, "a.bin"); Path(src).write_bytes(b"hello-\x00-data")
    enc = os.path.join(tmp, "a.enc"); out = os.path.join(tmp, "a.out")
    vault.encrypt_file(src, enc, pw)
    vault.decrypt_to_file(enc, out, pw)
    assert Path(out).read_bytes() == b"hello-\x00-data"

    print("VAULT TESTS PASSED ✅  (암복호화/잠금-해제/오류비번/검증)")


if __name__ == "__main__":
    main()
