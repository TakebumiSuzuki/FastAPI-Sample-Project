# DB を使わない JWT の検証部分のロジックをここに入れる
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

# 最新の推奨設定（Argon2id）を適用した pwdlib インスタンスを作っている
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict[str, Any]) -> str:
    settings = get_settings()

    expire = datetime.now(tz=UTC) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    to_encode = data.copy()
    # datetime 型を渡すと、pyjwt が裏で自動的に JWT 標準の数値
    # （UNIXタイムスタンプ：1970年からの経過秒数）へ変換してくれます。
    to_encode["exp"] = expire
    # access_token も refresh_token もデータとしては区別がない
    # typeはアプリ側が区別のために入れる独自項目です。
    to_encode["type"] = "access"
    to_encode["jti"] = str(uuid.uuid4())

    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return token


def create_refresh_token(data: dict[str, Any]) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(days=settings.refresh_token_expire_days)
    to_encode = data.copy()
    to_encode["exp"] = expire
    to_encode["type"] = "refresh"
    to_encode["jti"] = str(uuid.uuid4())

    token = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return token


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(
        token,
        key=settings.secret_key,
        algorithms=settings.algorithm,
    )
    if "type" not in payload or payload["type"] != expected_type:
        raise jwt.InvalidTokenError("unexpected token type")
    return payload
