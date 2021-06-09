import socket
import sys

import httpx
import pytest

from tests.utils import run_server
from uvicorn.config import Config


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
async def test_return_close_header():
    config = Config(app=app, host="localhost", loop="asyncio", limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:8000", headers={"connection": "close"}
            )

    assert response.status_code == 204
    assert (
        "connection" in response.headers and response.headers["connection"] == "close"
    )


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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Skipping uds test on Windows",
)
@pytest.mark.asyncio
async def test_run_uds(tmp_path):
    uds = str(tmp_path / "socket")
    config = Config(app=app, loop="asyncio", limit_max_requests=1, uds=uds)
    async with run_server(config):
        data = b"GET / HTTP/1.1\r\n\r\n"
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(uds)
            r = client.sendall(data)
            assert r is None
        finally:
            client.close()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Skipping uds test on Windows",
)
@pytest.mark.asyncio
async def test_run_fd(tmp_path):
    uds = str(tmp_path / "socket")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    fd = sock.fileno()
    sock.bind(uds)
    config = Config(app=app, loop="asyncio", limit_max_requests=1, fd=fd)
    async with run_server(config):
        data = b"GET / HTTP/1.1\r\n\r\n"
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            client.connect(uds)
            r = client.sendall(data)
            assert r is None
        finally:
            client.close()
            sock.close()
