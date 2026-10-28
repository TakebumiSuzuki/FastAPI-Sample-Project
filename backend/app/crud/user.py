import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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


async def create_user(db_session: AsyncSession, user_in: UserCreate) -> User:
    stmt = select(User).where(User.email == user_in.email)
    existing_user = (await db_session.execute(stmt)).scalar_one_or_none()
    if existing_user:
        raise UserAlreadyExists(user_email=existing_user.email)

    hashed_password = hash_password(user_in.password)
    new_user = User(email=user_in.email, hashed_password=hashed_password)
    db_session.add(new_user)
    await db_session.commit()
    await db_session.refresh(new_user)
    return new_user


dummy_hash = hash_password("dummy")


async def authenticate_user(
    db_session: AsyncSession,
    email: str,
    password: str,
) -> User | None:

    stmt = select(User).where(User.email == email)
    user = (await db_session.execute(stmt)).scalar_one_or_none()

    if verify_password(
        plain_password=password,
        hashed_password=user.hashed_password if user is not None else dummy_hash,
    ):
        return user

    return None


async def revoke_refresh_token(
    db_session: AsyncSession,
    refresh_token: str,
) -> None:
    stmt = select(RefreshToken).where(RefreshToken.refresh_token == refresh_token)
    token_record = (await db_session.execute(stmt)).scalar_one_or_none()
    if token_record is not None:
        token_record.active = False
        await db_session.commit()


async def register_refresh_token(
    db_session: AsyncSession,
    user_id: int,
    refresh_token: str,
) -> None:
    token = RefreshToken(user_id=user_id, refresh_token=refresh_token)
    db_session.add(token)
    await db_session.commit()


async def reissue_tokens(
    db_session: AsyncSession,
    refresh_token: str | None,
):
    if refresh_token is None:
        raise AuthenticationError()

    try:
        payload = decode_token(token=refresh_token, expected_type="refresh")
    except jwt.InvalidTokenError:
        raise AuthenticationError()

    stmt = select(RefreshToken).where(RefreshToken.refresh_token == refresh_token)
    stored_refresh_token = (await db_session.execute(stmt)).scalar_one_or_none()
    # refresh tokenがそもそもホワイトリストに登録されていなかった場合、または、
    # 既に revoke 済みになっていた場合(=盗まれて既に対処済み)
    if stored_refresh_token is None or not stored_refresh_token.active:
        raise AuthenticationError()
    stored_refresh_token.active = False

    user_id_str = payload["sub"]
    email = payload["email"]

    new_access_token = create_access_token(
        data={"sub": user_id_str, "email": email},
    )
    new_refresh_token = create_refresh_token(
        data={"sub": user_id_str, "email": email},
    )
    await register_refresh_token(
        db_session=db_session,
        user_id=int(user_id_str),
        refresh_token=new_refresh_token,
    )

    return new_access_token, new_refresh_token
