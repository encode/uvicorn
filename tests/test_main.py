import httpx
import pytest

from tests.conftest import run_server
from uvicorn.config import Config


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host, url",
    [
        pytest.param(None, "http://127.0.0.1:8000", id="default"),
        pytest.param("localhost", "http://127.0.0.1:8000", id="hostname"),
        pytest.param("::1", "http://[::1]:8000", id="ipv6"),
    ],
)
async def test_run(host, url):
    config = Config(app=app, host=host, loop="asyncio", limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_multiprocess():
    config = Config(app=app, loop="asyncio", workers=2, limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_reload():
    config = Config(app=app, loop="asyncio", reload=True, limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
    assert response.status_code == 204
