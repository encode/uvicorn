from tests.client import TestClient


async def hello_world(scope, receive, send):
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
