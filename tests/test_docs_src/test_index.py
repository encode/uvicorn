from docs.src.index.example import app
from tests.client import TestClient


def test_index_app():
    client = TestClient(app, base_url="http://testserver")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "Hello, world!"
