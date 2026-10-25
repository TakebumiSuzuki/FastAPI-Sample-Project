import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import verify_password
from app.models import RefreshToken, User


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


def test_login_user(
    db_session: Session,
    client: TestClient,
    seed_users,
):
    response = client.post(
        "/users/login",
        json={
            "email": "test_user_1@gmail.com",
            "password": "Test_password_1!",
        },
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.cookies
    assert "HttpOnly" in response.headers["set-cookie"]

    access_token = response.json()["access_token"]

    settings = get_settings()
    access_payload = jwt.decode(
        access_token,
        settings.secret_key,
        algorithms=[settings.algorithm],  # リストで渡す必要があります
    )
    assert access_payload["email"] == "test_user_1@gmail.com"
    assert access_payload["type"] == "access"

    refresh_token = response.cookies["refresh_token"]
    refresh_payload = jwt.decode(
        refresh_token,
        settings.secret_key,
        algorithms=[settings.algorithm],  # リストで渡す必要があります
    )
    assert refresh_payload["email"] == "test_user_1@gmail.com"
    assert refresh_payload["type"] == "refresh"

    stmt = select(RefreshToken).where(
        RefreshToken.refresh_token == refresh_token,
        RefreshToken.user_id == int(refresh_payload["sub"]),
    )
    saved_refresh_token = db_session.execute(stmt).scalar_one()
    assert saved_refresh_token is not None
    assert saved_refresh_token.refresh_token == refresh_token


@pytest.mark.parametrize(
    "email, password",
    [
        ("test_user_1@gmail.com", "Test_password_2!"),
        ("test_user_3@gmail.com", "Test_password_2!"),
    ],
)
def test_user_login_invalid_email_or_password(
    client: TestClient,
    seed_users,
    email: str,
    password: str,
):
    response = client.post("/users/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Incorrect email or password"


def test_user_login_invalid_email(
    client: TestClient,
    seed_users,
):
    response = client.post(
        "/users/login",
        json={
            "email": "test_email",
            "password": "Test_password_2!",
        },
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "validation_error"


def test_user_login_invalid_payload(
    client: TestClient,
    # seed_users, これは必要ない。なぜならDB照合前に弾かれるから。
):
    response = client.post(
        "/users/login",
        json={
            "email": "test_user_1@gmail.com",
            "password": "Test_password_1!",
            "another_key": "test_data",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_user_logout(db_session, logged_in_context):
    logged_in_client = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    refresh_token = logged_in_context["refresh_token"]

    jwt_payload = jwt.decode(
        access_token, key=get_settings().secret_key, algorithms=get_settings().algorithm
    )
    user_id = jwt_payload["sub"]
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.refresh_token == refresh_token,
    )
    result1 = db_session.execute(stmt).scalar_one_or_none()
    assert result1 is not None
    assert result1.active == True
    assert result1.refresh_token == refresh_token

    response = logged_in_client.post(
        "/users/logout", json={}, headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 204

    result2 = db_session.execute(stmt).scalar_one_or_none()
    assert result2 is not None
    assert result2.active == False
    assert "refresh_token" not in logged_in_client.cookies


def test_user_logout_by_unauthorized_user(client):
    response = client.post(
        "/users/logout",
        json={},
        # もし headers を渡さない場合、get_user 内のトークン検証に到達する前に FastAPIの標準機能で弾かれ、code が "invalid_credentials" ではなく"http_error"（※ヘッダーが存在しないという共通エラー）になります。
        headers={"Authorization": "Bearer fake_access_token"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "invalid_credentials"
