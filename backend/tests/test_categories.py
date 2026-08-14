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


def test_create_category(client):
    response = client.post("/categories", json={"name": "foods"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "foods"


def test_create_category_name_too_short(client):
    response = client.post("/categories", json={"name": "sa"})
    assert response.status_code == 422


def test_create_category_name_too_long(client):
    long_char = "a" * 31
    response = client.post("/categories", json={"name": long_char})
    assert response.status_code == 422


def test_create_category_extra_field_forbidden(client):
    response = client.post("/categories", json={"name": "ust", "extra_field": "value"})
    assert response.status_code == 422
