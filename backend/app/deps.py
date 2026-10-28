from collections.abc import AsyncGenerator
from typing import Annotated, Any

import jwt
from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.session import SessionLocal
from app.exceptions import AuthenticationError
from app.models import User


class CommonQueryParams:
    def __init__(
        self,
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ):
        self.skip = skip
        self.limit = limit


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        await db_session.close()


async def get_user(
    db_session: Annotated[AsyncSession, Depends(get_db_session)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> User:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        if payload.get("type") != "access":
            raise AuthenticationError()
        id = int(payload["sub"])
    except jwt.InvalidTokenError, KeyError, ValueError:
        raise AuthenticationError()

    # select(User).where(User.id == id) を書いて scalar_one_or_none() するのと同じ
    user = await db_session.get(User, id)
    if not user or user.is_active == False:
        raise AuthenticationError()
    return user
