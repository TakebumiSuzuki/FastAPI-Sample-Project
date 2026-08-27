from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    # レスポンスの JSON ボディを検証、jsonメソッドのところは parse_json などの名前の方が実態に合う。
    data = response.json()
    assert "message" in data
    assert data["message"] == "Hello, FastAPI!"
