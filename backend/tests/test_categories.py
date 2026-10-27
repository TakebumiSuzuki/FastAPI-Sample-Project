from fastapi.testclient import TestClient

from app.models.category import Category


def test_get_categories(client, db_session):
    sneakers = Category(name="sneakers")
    cosmetics = Category(name="cosmetics")
    db_session.add_all([sneakers, cosmetics])
    db_session.commit()

    response = client.get("/categories")
    assert response.status_code == 200
    data = response.json()
    assert data[0]["name"] == "sneakers"
    assert data[1]["name"] == "cosmetics"


def test_create_category(logged_in_context):
    logged_in_client: TestClient = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    response = logged_in_client.post(
        "/categories",
        json={"name": "foods"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "foods"


def test_create_category_name_too_short(logged_in_context):
    logged_in_client: TestClient = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    response = logged_in_client.post(
        "/categories",
        json={"name": "sa"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert "name" in details


def test_create_category_name_min_length_ok(logged_in_context):
    logged_in_client: TestClient = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    response = logged_in_client.post(
        "/categories",
        json={"name": "sal"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201


def test_create_category_name_max_length_ok(logged_in_context):
    logged_in_client: TestClient = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    response = logged_in_client.post(
        "/categories",
        json={"name": "a" * 30},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 201


def test_create_category_name_too_long(logged_in_context):
    logged_in_client: TestClient = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    response = logged_in_client.post(
        "/categories",
        json={"name": "a" * 31},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert "name" in details


def test_create_category_extra_field_forbidden(logged_in_context):
    logged_in_client: TestClient = logged_in_context["logged_in_client"]
    access_token = logged_in_context["access_token"]
    response = logged_in_client.post(
        "/categories",
        json={"name": "ust", "extra_field": "value"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert "extra_field" in details


def test_create_category_unauthorized(client: TestClient):
    response = client.post(
        "/categories",
        json={"name": "foods"},
    )
    assert response.status_code == 401
    # ヘッダーなしでリクエストした場合は code が "invalid_credentials" ではなく"http_error" になる
    assert response.json()["error"]["code"] == "http_error"
