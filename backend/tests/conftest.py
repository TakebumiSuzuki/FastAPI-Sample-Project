from collections.abc import AsyncGenerator

import pytest

# Uvicorn の代わりに pytest-asyncioが非同期処理の実行エンジンであるイベントループを起動し、
# その上で動きます。そこでブラウザ役の AsyncClientが送ったリクエストを、Uvicorn の
# 変換役を兼ねる ASGITransport が ASGI 規格の3引数に変換して
# await app(scope, receive, send) と app を直接呼び出します。
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# sqlalchemy.poolには全7種類（基本5種類＋非同期用QueuePool2種類）のプールが存在し、
# 通常のデフォルトは QueuePool（非同期はAsyncAdaptedQueuePool）
# PostgreSQL で非同期テストを書くときは NullPool を使う
from sqlalchemy.pool import StaticPool

from app.crud.user import create_user
from app.deps import get_db_session
from app.models import Base
from app.schemas import UserCreate
from main import app

engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingAsyncSessionLocal = async_sessionmaker(
    autoflush=False, bind=engine, expire_on_commit=False
)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession]:
    # engine.begin() は、 engine.connect()（コネクション生成＋DB接続）と
    # conn.begin()（自動 commit/rollback を担うトランザクション管理オブジェクト生成）を
    # まとめて行い、変数 conn にコネクション（AsyncConnection）を渡すショートカット。
    # ここでのトランザクションオブジェクトは Core の方のもの。
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = TestingAsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    async with AsyncClient(
        # http://test は、URLの形式チェックを通すためのダミーの文字列。
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def seed_users(db_session: AsyncSession):
    users_data = [
        {"email": "test_user_1@gmail.com", "password": "Test_password_1!"},
        {"email": "test_user_2@gmail.com", "password": "Test_password_2!"},
    ]

    for user_data in users_data:
        user_in = UserCreate.model_validate(user_data)
        await create_user(db_session=db_session, user_in=user_in)


@pytest.fixture()
async def logged_in_context(client, seed_users):
    response = await client.post(
        "/users/login",
        json={
            "email": "test_user_1@gmail.com",
            "password": "Test_password_1!",
        },
    )
    access_token = response.json()["access_token"]
    refresh_token = response.cookies["refresh_token"]
    return {
        "logged_in_client": client,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
