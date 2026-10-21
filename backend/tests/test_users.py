from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import User


def test_register_user(db_session: Session, client: TestClient):
    response = client.post(
        "/users",
        json={"email": "test_user@gmail.com", "password": "password1234"},
    )
    assert response.status_code == 201

    data = response.json()
    assert "password" not in data
    assert "hashed_password" not in data
    assert data["email"] == "test_user@gmail.com"

    stmt = select(User).where(User.email == "test_user@gmail.com")
    user = db_session.execute(stmt).scalar_one_or_none()
    assert user is not None
    assert user.email == "test_user@gmail.com"
    assert verify_password("password1234", user.hashed_password)


def test_register_duplicate_email(client: TestClient):
    response = client.post(
        "/users",
        json={"email": "test_user@gmail.com", "password": "password1234"},
    )
    assert response.status_code == 201

    response2 = client.post(
        "/users",
        json={"email": "test_user@gmail.com", "password": "password4321"},
    )
    assert response2.status_code == 409
    data = response2.json()
    assert data["error"]["code"] == "user_already_exists"


def test_register_invalid_password():
    pass


def test_login_user():
    pass
