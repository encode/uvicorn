import pytest

from tests.client import TestClient


def hello_world(scope):
    async def asgi(receive, send):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send(
            {"type": "http.response.body", "body": b"hello, world", "more_body": False}
        )

    return asgi


def test_explicit_base_url():
    client = TestClient(hello_world, base_url="http://testserver:321")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "hello, world"


def test_explicit_host():
    client = TestClient(hello_world)
    response = client.get("/", headers={"host": "example.org"})
    assert response.status_code == 200
    assert response.text == "hello, world"
