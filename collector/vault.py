"""마스터 비밀번호 기반 중앙 DB 암호화 (at-rest).

설계
----
평문 SQLite 작업 파일로 동작하되, '잠금' 상태에서는 그 파일을 암호화한 **볼트(.enc)**
로만 디스크에 둔다.
  * unlock : 볼트를 복호화해 작업 파일 생성 (없으면 빈 작업 파일 = 새 볼트)
  * lock   : 작업 파일을 다시 암호화해 볼트에 저장하고 평문 작업 파일을 삭제

암호화: `cryptography`(Fernet = AES-128-CBC + HMAC) + scrypt KDF.
이 패키지가 없으면 암호화 기능만 비활성화되고, 평문 모드는 그대로 동작한다.

한계(정직하게): 앱이 '실행 중'인 동안에는 복호화된 작업 파일이 디스크에 존재한다
(수집기와 서버가 같은 DB를 공유해야 하므로). 작업 파일은 0600 권한으로 두고 종료 시
삭제한다. 더 강한 보장이 필요하면 SQLCipher(네이티브 의존성)가 대안이다.
"""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import struct
import tempfile
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
    _HAVE_CRYPTO = True
except Exception:  # pragma: no cover
    _HAVE_CRYPTO = False

MAGIC = b"BHVAULT1"
# n=2^15 scrypt → 약 32MiB 필요. OpenSSL 기본 한도(32MiB)를 넘기지 않도록 maxmem 상향.
_SCRYPT = dict(n=2 ** 15, r=8, p=1, maxmem=96 * 1024 * 1024, dklen=32)


def available() -> bool:
    """암호화 사용 가능 여부(cryptography 설치됨)."""
    return _HAVE_CRYPTO


def _require():
    if not _HAVE_CRYPTO:
        raise RuntimeError(
            "암호화 기능은 'cryptography' 패키지가 필요합니다:  pip install cryptography")


def _derive_key(password: str, salt: bytes) -> bytes:
    raw = hashlib.scrypt(password.encode("utf-8"), salt=salt, **_SCRYPT)
    return base64.urlsafe_b64encode(raw)


def encrypt_file(plain_path, vault_path, password, salt=None):
    _require()
    salt = salt or secrets.token_bytes(16)
    token = Fernet(_derive_key(password, salt)).encrypt(Path(plain_path).read_bytes())
    blob = MAGIC + struct.pack("<H", len(salt)) + salt + token
    Path(vault_path).write_bytes(blob)


def decrypt_to_file(vault_path, plain_path, password):
    _require()
    blob = Path(vault_path).read_bytes()
    if blob[:8] != MAGIC:
        raise ValueError("볼트 형식이 아닙니다.")
    (slen,) = struct.unpack("<H", blob[8:10])
    salt = blob[10:10 + slen]
    token = blob[10 + slen:]
    try:
        data = Fernet(_derive_key(password, salt)).decrypt(token)
    except InvalidToken:
        raise ValueError("비밀번호가 틀렸거나 볼트가 손상되었습니다.")
    Path(plain_path).write_bytes(data)
    try:
        os.chmod(plain_path, 0o600)
    except OSError:
        pass


def verify_password(vault_path, password) -> bool:
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tmp = tf.name
        decrypt_to_file(vault_path, tmp, password)
        os.remove(tmp)
        return True
    except Exception:
        return False


class VaultSession:
    """unlock → 작업 DB 경로 제공 → lock(재암호화 + 평문 삭제)."""

    def __init__(self, vault_path, password, work_path=None):
        self.vault_path = Path(vault_path)
        self.password = password
        self.work_path = Path(work_path) if work_path else self.vault_path.with_suffix(".work.db")

    def unlock(self) -> str:
        _require()
        if self.vault_path.exists():
            decrypt_to_file(self.vault_path, self.work_path, self.password)
        else:  # 새 볼트: 빈 작업 파일 (db.connect가 스키마를 생성)
            self.work_path.write_bytes(b"")
            try:
                os.chmod(self.work_path, 0o600)
            except OSError:
                pass
        return str(self.work_path)

    def lock(self):
        if self.work_path.exists():
            encrypt_file(self.work_path, self.vault_path, self.password)
            try:
                os.remove(self.work_path)
            except OSError:
                pass


def open_db(db_arg, vault_arg):
    """CLI 공용 헬퍼: vault면 unlock된 작업 경로와 세션을, 아니면 (db경로, None)을 반환."""
    if vault_arg:
        import getpass
        _require()
        pw = os.environ.get("BHIST_PASSWORD") or getpass.getpass("마스터 비밀번호: ")
        sess = VaultSession(vault_arg, pw)
        return sess.unlock(), sess
    return db_arg, None


def main(argv=None):
    import argparse
    import getpass

    ap = argparse.ArgumentParser(description="중앙 DB 암호화 볼트 관리")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pi = sub.add_parser("init", help="빈 암호화 볼트 생성")
    pi.add_argument("--vault", required=True)
    ps = sub.add_parser("info", help="암호화 사용 가능/볼트 여부 확인")
    ps.add_argument("--vault")
    args = ap.parse_args(argv)

    if args.cmd == "info":
        print("cryptography:", "사용 가능" if available() else "미설치")
        if args.vault:
            p = Path(args.vault)
            print("볼트 파일:", "있음" if p.exists() else "없음", f"({p})")
        return

    if args.cmd == "init":
        _require()
        if Path(args.vault).exists():
            raise SystemExit("이미 존재하는 볼트입니다.")
        pw = os.environ.get("BHIST_PASSWORD") or getpass.getpass("새 마스터 비밀번호: ")
        if not os.environ.get("BHIST_PASSWORD"):
            if pw != getpass.getpass("한 번 더: "):
                raise SystemExit("비밀번호가 일치하지 않습니다.")
        sess = VaultSession(args.vault, pw)
        sess.unlock()  # 빈 작업 파일
        sess.lock()    # 즉시 암호화
        print(f"볼트 생성 완료 ✅  {args.vault}")


if __name__ == "__main__":
    main()
