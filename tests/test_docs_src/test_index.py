from docs.src.index import example_app
from tests.client import TestClient


def test_index_app():
    client = TestClient(example_app, base_url="http://testserver")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "Hello, world!"
