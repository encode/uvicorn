import asyncio

import httpx
import pytest

from uvicorn import Config, Server


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.fixture
def server_fixture(event_loop, config_arg):
    server = Server(config=config_arg)
    cancel_handle = asyncio.ensure_future(server.serve(), loop=event_loop)
    event_loop.run_until_complete(asyncio.sleep(0.1))
    try:
        yield
    finally:
        event_loop.run_until_complete(server.shutdown())
        cancel_handle.cancel()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_arg", [Config(app=app, loop="asyncio", limit_max_requests=1)]
)
async def test_default_default_headers(server_fixture, config_arg):
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8000")
    assert response.headers["server"] == "uvicorn" and response.headers["date"]


# fmt: off
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_arg", [Config(app=app, loop="asyncio", limit_max_requests=1, headers=[("Server", "over-ridden")])]  # noqa: E501
)
# fmt: on
async def test_override_server_header(server_fixture, config_arg):
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8000")
    assert response.headers["server"] == "over-ridden" and response.headers["date"]


# fmt: off
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_arg", [Config(app=app, loop="asyncio", limit_max_requests=1, headers=[("Server", "over-ridden"), ("Server", "another-value")])]  # noqa: E501
)
# fmt: on
async def test_override_server_header_multiple_times(server_fixture, config_arg):
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8000")
    assert (
        response.headers["server"] == "over-ridden, another-value"
        and response.headers["date"]
    )


# fmt: off
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config_arg", [Config(app=app, loop="asyncio", limit_max_requests=1, headers=[("X-Additional", "new-value")])]  # noqa: E501
)
# fmt: on
async def test_add_additional_header(server_fixture, config_arg):
    async with httpx.AsyncClient() as client:
        response = await client.get("http://127.0.0.1:8000")
    assert (
        response.headers["x-additional"] == "new-value"
        and response.headers["server"] == "uvicorn"
        and response.headers["date"]
    )
