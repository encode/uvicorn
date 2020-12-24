import asyncio

import pytest

from tests.client import TestClient
from uvicorn.middleware.debug import DebugMiddleware


def test_debug_text():
    async def app(scope, receive, send):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    assert "RuntimeError" in response.text


def test_debug_html():
    async def app(scope, receive, send):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/", headers={"Accept": "text/html, */*"})
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    assert "RuntimeError" in response.text


def test_debug_after_response_sent():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 204
    assert response.content == b""


def test_debug_not_http():
    async def app(scope, send, receive):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)

    loop = asyncio.new_event_loop()
    with pytest.raises(RuntimeError):
        loop.run_until_complete(app({"type": "websocket"}, None, None))
    loop.close()
