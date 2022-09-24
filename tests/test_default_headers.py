import asyncio
import datetime as dt

import anyio
import anyio.abc
import httpx
import pytest

from tests.utils import run_server
from uvicorn import Config

DATE_FORMAT = "%a, %d %b %Y %H:%M:%S GMT"


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


@pytest.mark.anyio
async def test_date_headers_update():
    config = Config(app=app, loop="asyncio")
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
            date = response.headers["date"]
            first_date = dt.datetime.strptime(date, DATE_FORMAT)
            second_date = first_date

            cancelled = False

            async def sleep_and_cancel(tg: anyio.abc.TaskGroup):
                nonlocal cancelled
                await asyncio.sleep(2)
                cancelled = True
                await tg.cancel_scope.cancel()

            async def ensure_different_date(tg: anyio.abc.TaskGroup):
                nonlocal second_date
                async with httpx.AsyncClient() as client:
                    while second_date == first_date:
                        response = await client.get("http://127.0.0.1:8000")
                        date = response.headers["date"]
                        second_date = dt.datetime.strptime(date, DATE_FORMAT)
                tg.cancel_scope.cancel()

            async with anyio.create_task_group() as tg:
                tg.start_soon(sleep_and_cancel, tg)
                tg.start_soon(ensure_different_date, tg)

            assert not cancelled
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
