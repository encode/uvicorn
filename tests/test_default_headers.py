import httpx
import pytest

from tests.utils import run_server
from uvicorn import Config


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
async def test_default_default_headers(unused_tcp_port):
    config = Config(app=app, port=unused_tcp_port, loop="asyncio", limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert response.headers["server"] == "uvicorn" and response.headers["date"]


@pytest.mark.asyncio
async def test_override_server_header(unused_tcp_port):
    config = Config(
        app=app,
        port=unused_tcp_port,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("Server", "over-ridden")],
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert (
                response.headers["server"] == "over-ridden" and response.headers["date"]
            )


@pytest.mark.asyncio
async def test_disable_default_server_header(unused_tcp_port):
    config = Config(
        app=app,
        port=unused_tcp_port,
        loop="asyncio",
        limit_max_requests=1,
        server_header=False,
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert "server" not in response.headers


@pytest.mark.asyncio
async def test_override_server_header_multiple_times(unused_tcp_port):
    config = Config(
        app=app,
        port=unused_tcp_port,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("Server", "over-ridden"), ("Server", "another-value")],
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert (
                response.headers["server"] == "over-ridden, another-value"
                and response.headers["date"]
            )


@pytest.mark.asyncio
async def test_add_additional_header(unused_tcp_port):
    config = Config(
        app=app,
        port=unused_tcp_port,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("X-Additional", "new-value")],
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert (
                response.headers["x-additional"] == "new-value"
                and response.headers["server"] == "uvicorn"
                and response.headers["date"]
            )


@pytest.mark.asyncio
async def test_disable_default_date_header(unused_tcp_port):
    config = Config(
        app=app,
        port=unused_tcp_port,
        loop="asyncio",
        limit_max_requests=1,
        date_header=False,
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert "date" not in response.headers
