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
    # hashed_password の前半から、アルゴリズム名・バージョン・計算設定・ソルトを取り出し、
    # それを使って、plain_password を同じ条件でハッシュ化し、比較する。
    return password_hash.verify(plain_password, hashed_password)


# トークンの作られ方（access, refresh 両方同じ）
#   1. ヘッダーとペイロードを、それぞれ個別に Base64URL エンコードし、.(ドッド)で繋ぐ。
#   ヘッダーには、 {"alg": "HS256", "typ": "JWT"}　のような情報が入る。
#   2. 繋いだ文字列にアプリの secret_key を加えてハッシュ計算を行い、その結果も
#   Base64URL エンコードして「署名」を作る。
#   3. 最後に署名を . でくっつけて、ヘッダー.ペイロード.署名 の形にする。
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
    # typeはアプリ側が区別のために入れる独自項目。
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
