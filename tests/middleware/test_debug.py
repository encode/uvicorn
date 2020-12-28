import httpx
import pytest

from uvicorn.middleware.debug import DebugMiddleware


@pytest.mark.asyncio
async def test_debug_text():
    async def app(scope, receive, send):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/plain")
    assert "RuntimeError" in response.text


@pytest.mark.asyncio
async def test_debug_html():
    async def app(scope, receive, send):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/", headers={"Accept": "text/html, */*"})
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("text/html")
    assert "RuntimeError" in response.text


@pytest.mark.asyncio
async def test_debug_after_response_sent():
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/")
    assert response.status_code == 204
    assert response.content == b""


@pytest.mark.asyncio
async def test_debug_not_http():
    async def app(scope, send, receive):
        raise RuntimeError("Something went wrong")

    app = DebugMiddleware(app)
    with pytest.raises(RuntimeError):
        await app({"type": "websocket"}, None, None)
