"""Fernet 对称加密：用于 SSH 密码 / repo token / SMTP 授权码落库加密。"""
import os

from cryptography.fernet import Fernet, InvalidToken

from app.config import SECRET_KEY, SECRET_KEY_FILE


def _load_key() -> bytes:
    if SECRET_KEY:
        return SECRET_KEY.encode()
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    SECRET_KEY_FILE.write_bytes(key)
    os.chmod(SECRET_KEY_FILE, 0o600)
    return key


_fernet = Fernet(_load_key())


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return _fernet.encrypt(plain.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet.decrypt(token.encode()).decode()
    except InvalidToken:
        return ""


MASK = "******"


def mask(value: str) -> str:
    return MASK if value else ""
