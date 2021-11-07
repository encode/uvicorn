from logging import WARNING

import httpx
import pytest

from tests.utils import run_server
from uvicorn.config import Config
from uvicorn.main import run


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
async def test_return_close_header(unused_tcp_port):
    config = Config(
        app=app,
        host="localhost",
        port=unused_tcp_port,
        loop="asyncio",
        limit_max_requests=1,
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://127.0.0.1:{unused_tcp_port}", headers={"connection": "close"}
            )

    assert response.status_code == 204
    assert (
        "connection" in response.headers and response.headers["connection"] == "close"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "host, url",
    [
        pytest.param(None, "http://127.0.0.1", id="default"),
        pytest.param("localhost", "http://127.0.0.1", id="hostname"),
        pytest.param("::1", "http://[::1]", id="ipv6"),
    ],
)
async def test_run(host, url, unused_tcp_port):
    config = Config(
        app=app, host=host, port=unused_tcp_port, loop="asyncio", limit_max_requests=1
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}:{unused_tcp_port}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_multiprocess(unused_tcp_port):
    config = Config(
        app=app, port=unused_tcp_port, loop="asyncio", workers=2, limit_max_requests=1
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_run_reload(unused_tcp_port):
    config = Config(
        app=app, port=unused_tcp_port, loop="asyncio", reload=True, limit_max_requests=1
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
    assert response.status_code == 204


def test_run_invalid_app_config_combination(caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(SystemExit) as exit_exception:
        run(app, reload=True)
    assert exit_exception.value.code == 1
    assert caplog.records[-1].name == "uvicorn.error"
    assert caplog.records[-1].levelno == WARNING
    assert caplog.records[-1].message == (
        "You must pass the application as an import string to enable "
        "'reload' or 'workers'."
    )
