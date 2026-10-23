from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.user import create_user
from app.deps import get_db_session
from app.models import Base
from app.schemas import UserCreate
from main import app

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session() -> Generator[Session]:
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient]:
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def seed_users(db_session: Session):
    users_data = [
        {"email": "test_user_1@gmail.com", "password": "Test_password_1!"},
        {"email": "test_user_2@gmail.com", "password": "Test_password_2!"},
    ]

    for user_data in users_data:
        user_in = UserCreate.model_validate(user_data)
        create_user(db_session=db_session, user_in=user_in)
