import jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.exceptions import AuthenticationError, UserAlreadyExists
from app.models import RefreshToken, User
from app.schemas import UserCreate


def create_user(db_session: Session, user_in: UserCreate) -> User:
    stmt = select(User).where(User.email == user_in.email)
    existing_user = db_session.execute(stmt).scalar_one_or_none()
    if existing_user:
        raise UserAlreadyExists(user_email=existing_user.email)

    hashed_password = hash_password(user_in.password)
    new_user = User(email=user_in.email, hashed_password=hashed_password)
    db_session.add(new_user)
    db_session.commit()
    db_session.refresh(new_user)
    return new_user


dummy_hash = hash_password("dummy")


def authenticate_user(
    db_session: Session,
    email: str,
    password: str,
) -> User | None:

    stmt = select(User).where(User.email == email)
    user = db_session.execute(stmt).scalar_one_or_none()

    if verify_password(
        plain_password=password,
        hashed_password=user.hashed_password if user is not None else dummy_hash,
    ):
        return user

    return None


def revoke_refresh_token(
    db_session: Session,
    refresh_token: str,
) -> None:
    stmt = select(RefreshToken).where(RefreshToken.refresh_token == refresh_token)
    # refresh_token の expは秒単位なので、同一人物が高速にログインすると全く
    # 同じ文字列の refresh_tokenを連続して取得することになる。
    token_records = db_session.execute(stmt).scalars().all()

    for token_record in token_records:
        token_record.active = False

    db_session.commit()


def register_refresh_token(
    db_session: Session,
    user_id: int,
    refresh_token: str,
) -> None:
    token = RefreshToken(user_id=user_id, refresh_token=refresh_token)
    db_session.add(token)
    db_session.commit()


def reissue_tokens(
    db_session: Session,
    refresh_token: str | None,
):
    if refresh_token is None:
        raise AuthenticationError()

    try:
        payload = decode_token(token=refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise AuthenticationError()

    stmt = select(RefreshToken).where(RefreshToken.refresh_token == refresh_token)
    stored_refresh_tokens = db_session.execute(stmt).scalars()
    tokens_to_revoke = []
    for tk in stored_refresh_tokens:
        if tk.active == True:
            tokens_to_revoke.append(tk)
            tk.active = False
    # refresh tokenがそもそもホワイトリストに登録されていなかった場合、または、
    # 全て revoke 済みになっていた場合(=盗まれて既に対処済み)
    if len(tokens_to_revoke) == 0:
        raise AuthenticationError()

    user_id_str = payload["sub"]
    email = payload["email"]

    new_access_token = create_access_token(
        data={"sub": user_id_str, "email": email},
    )
    new_refresh_token = create_refresh_token(
        data={"sub": user_id_str, "email": email},
    )
    register_refresh_token(
        db_session=db_session,
        user_id=int(user_id_str),
        refresh_token=new_refresh_token,
    )

    return new_access_token, new_refresh_token
