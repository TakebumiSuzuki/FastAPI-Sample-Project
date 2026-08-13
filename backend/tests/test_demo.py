from fastapi.testclient import TestClient 
from main import app 

client = TestClient(app) 

def test_read_root():
        response = client.get("/")
        assert response.status_code == 200
        # レスポンスの JSON ボディを検証
        data = response.json()
        assert "message" in data
        assert data["message"] == "Hello, FastAPI!"