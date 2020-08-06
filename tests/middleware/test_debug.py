import asyncio

import pytest

from tests.client import TestClient
from uvicorn._types import ASGI3App, Receive, Scope, Send
from uvicorn.middleware.debug import DebugMiddleware


def test_debug_text() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> ASGI3App:
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    assert "RuntimeError" in response.text


def test_debug_html() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> ASGI3App:
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/", headers={"Accept": "text/html, */*"})
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    assert "RuntimeError" in response.text


def test_debug_after_response_sent() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> ASGI3App:
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 204
    assert response.content == b""


def test_debug_not_http() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> ASGI3App:
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)

    with pytest.raises(RuntimeError):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(app({"type": "websocket"}, None, None))
