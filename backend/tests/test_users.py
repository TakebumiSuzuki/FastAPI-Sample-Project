import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import User


@pytest.mark.parametrize(
    "email, password",
    [
        ("test_user0@gmail.com", "Password1234!"),
        ("test_user1@gmail.com", "Passwd1!"),
        ("test_user2@gmail.com", "Pa1!" + "a" * 251),
    ],
)
def test_register_user(
    db_session: Session, client: TestClient, email: str, password: str
):
    response = client.post(
        "/users",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201

    data = response.json()
    assert "password" not in data
    assert "hashed_password" not in data
    assert data["email"] == email

    stmt = select(User).where(User.email == email)
    user = db_session.execute(stmt).scalar_one_or_none()
    assert user is not None
    assert user.email == email
    assert verify_password(password, user.hashed_password)


def test_register_duplicate_email(client: TestClient):
    response = client.post(
        "/users",
        json={"email": "test_user@gmail.com", "password": "Password1234!"},
    )
    assert response.status_code == 201

    response2 = client.post(
        "/users",
        json={"email": "test_user@gmail.com", "password": "Password4321!"},
    )
    assert response2.status_code == 409
    data = response2.json()
    assert data["error"]["code"] == "user_already_exists"


@pytest.mark.parametrize(
    "password",
    [
        "NoSpecialChar0",
        "nouppercase0!",
        "noNumber!",
        "NOLOWERCASE0!",
        "a1!A" + "a" * 252,
        "Test1!a",
    ],
)
def test_register_invalid_password(client: TestClient, password: str):
    response = client.post(
        "/users", json={"email": "test_user@gmail.com", "password": password}
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"
    assert "password" in data["error"]["details"]


def test_login_user():
    pass
