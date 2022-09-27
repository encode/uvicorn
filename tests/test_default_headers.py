import asyncio
import datetime
import datetime as dt
import sys

import httpx
import pytest

from tests.utils import run_server
from uvicorn import Config


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.anyio
async def test_default_default_headers():
    config = Config(app=app, loop="asyncio", limit_max_requests=1)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            assert response.headers["server"] == "uvicorn" and response.headers["date"]


@pytest.mark.skipif(
    sys.platform != "linux",
    reason="This fails on other OSs. If you know why, please help us.",
)
@pytest.mark.anyio
async def test_date_headers_update():  # pragma: no cover
    print(f"\ntest: {datetime.datetime.utcnow()}")
    config = Config(app=app, loop="asyncio")
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            date = response.headers["date"]
            first_date = dt.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z")
            print(first_date)

            await asyncio.sleep(1)

            response = await client.get("http://127.0.0.1:8000")
            date = response.headers["date"]
            second_date = dt.datetime.strptime(date, "%a, %d %b %Y %H:%M:%S %Z")
            print(second_date)

            assert second_date - first_date == dt.timedelta(seconds=1)


@pytest.mark.anyio
async def test_override_server_header():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("Server", "over-ridden")],
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            assert (
                response.headers["server"] == "over-ridden" and response.headers["date"]
            )


@pytest.mark.anyio
async def test_disable_default_server_header():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        server_header=False,
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            assert "server" not in response.headers


@pytest.mark.anyio
async def test_override_server_header_multiple_times():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("Server", "over-ridden"), ("Server", "another-value")],
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            assert (
                response.headers["server"] == "over-ridden, another-value"
                and response.headers["date"]
            )


@pytest.mark.anyio
async def test_add_additional_header():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("X-Additional", "new-value")],
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            assert (
                response.headers["x-additional"] == "new-value"
                and response.headers["server"] == "uvicorn"
                and response.headers["date"]
            )


@pytest.mark.anyio
async def test_disable_default_date_header():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        date_header=False,
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            assert "date" not in response.headers
