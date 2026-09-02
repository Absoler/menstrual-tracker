"""注册登录辅助：密码哈希与签名令牌。"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import HTTPException, Request

from . import db

TOKEN_TTL = 30 * 24 * 3600  # 30 天
PBKDF2_ITERATIONS = 200_000
SECRET_FILE = db.DATA_DIR / "secret.key"


def _get_secret() -> bytes:
    """首次运行生成随机密钥，之后复用；密钥丢失会使所有登录失效。"""
    if SECRET_FILE.exists():
        return SECRET_FILE.read_bytes()
    db.DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret = secrets.token_bytes(32)
    SECRET_FILE.write_bytes(secret)
    os.chmod(SECRET_FILE, 0o600)
    return secret


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _algo, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def create_token(user_id: int, username: str) -> str:
    payload = {"uid": user_id, "name": username, "exp": int(time.time()) + TOKEN_TTL}
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode())
    sig = _b64encode(hmac.new(_get_secret(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"


def decode_token(token: str) -> dict | None:
    try:
        body, sig = token.split(".")
        expected = _b64encode(
            hmac.new(_get_secret(), body.encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(_b64decode(body))
        if payload.get("exp", 0) < time.time():
            return None
        return payload
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


def get_current_user(request: Request) -> dict:
    """FastAPI 依赖：从 Authorization 头解析当前用户。"""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    payload = decode_token(header.removeprefix("Bearer "))
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"id": payload["uid"], "username": payload["name"]}


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
