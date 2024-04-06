import asyncio
import inspect
import socket
from logging import WARNING
from typing import Literal

import anyio
import httpx
import pytest

from tests.utils import run_server
from uvicorn import Server
from uvicorn.config import Config
from uvicorn.main import run


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


def _has_ipv6(host):
    sock = None
    has_ipv6 = False
    if socket.has_ipv6:
        try:
            sock = socket.socket(socket.AF_INET6)
            sock.bind((host, 0))
            has_ipv6 = True
        except Exception:  # pragma: no cover
            pass
    if sock:
        sock.close()
    return has_ipv6


@pytest.mark.anyio
@pytest.mark.parametrize(
    "host, url",
    [
        pytest.param(None, "http://127.0.0.1", id="default"),
        pytest.param("localhost", "http://127.0.0.1", id="hostname"),
        pytest.param(
            "::1",
            "http://[::1]",
            id="ipv6",
            marks=pytest.mark.skipif(not _has_ipv6("::1"), reason="IPV6 not enabled"),
        ),
    ],
)
async def test_run(host, url: str, unused_tcp_port: int):
    config = Config(app=app, host=host, loop="asyncio", limit_max_requests=1, port=unused_tcp_port)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}:{unused_tcp_port}")
    assert response.status_code == 204


@pytest.mark.anyio
async def test_run_multiprocess(unused_tcp_port: int):
    config = Config(app=app, loop="asyncio", workers=2, limit_max_requests=1, port=unused_tcp_port)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
    assert response.status_code == 204


@pytest.mark.anyio
async def test_run_reload(unused_tcp_port: int):
    config = Config(app=app, loop="asyncio", reload=True, limit_max_requests=1, port=unused_tcp_port)
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
        "You must pass the application as an import string to enable " "'reload' or 'workers'."
    )


def test_run_startup_failure(caplog: pytest.LogCaptureFixture) -> None:
    async def app(scope, receive, send):
        assert scope["type"] == "lifespan"
        message = await receive()
        if message["type"] == "lifespan.startup":
            raise RuntimeError("Startup failed")

    with pytest.raises(SystemExit) as exit_exception:
        run(app, lifespan="on")
    assert exit_exception.value.code == 3


def test_run_match_config_params() -> None:
    config_params = {
        key: repr(value)
        for key, value in inspect.signature(Config.__init__).parameters.items()
        if key not in ("self", "timeout_notify", "callback_notify")
    }
    run_params = {
        key: repr(value) for key, value in inspect.signature(run).parameters.items() if key not in ("app_dir",)
    }
    assert config_params == run_params


@pytest.mark.anyio
async def test_exit_on_create_server_with_invalid_host() -> None:
    with pytest.raises(SystemExit) as exc_info:
        config = Config(app=app, host="illegal_host")
        server = Server(config=config)
        await server.serve()
    assert exc_info.value.code == 1


@pytest.mark.anyio
@pytest.mark.parametrize("lifespan", ["auto", "on"])
@pytest.mark.parametrize("reraise", [True, False])
async def test_app_shutdown_failure_message_before_server_shutdown(
    lifespan: Literal["auto", "on"],
    reraise: bool,
    caplog: pytest.LogCaptureFixture,
    unused_tcp_port: int,
) -> None:
    # Test that the server shuts down if a lifespan.shutdown.failed message is sent
    # before the `Server.shutdown()` method is called.
    # This simulates the behavior of an application with a lifespan context manager
    # that raises an exception while the lifespan task is awaiting `receive()` after
    # having sent a lifespan.startup.complete message.

    event = asyncio.Event()

    async def lifespan_task() -> None:
        await event.wait()
        raise RuntimeError("Shutdown failed")

    async def app_(scope, receive, send):
        message = await receive()
        if message["type"] == "lifespan.startup":
            try:
                async with anyio.create_task_group() as tg:
                    tg.start_soon(lifespan_task)
                    await send({"type": "lifespan.startup.complete"})
                    await receive()
            except Exception:
                await send({"type": "lifespan.shutdown.failed", "message": "Shutdown failed"})

                if reraise:
                    raise

        await app(scope, receive, send)

    config = Config(app=app_, loop="asyncio", lifespan=lifespan, port=unused_tcp_port)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
            assert response.status_code == 204

        event.set()
        await asyncio.sleep(0.1)

        async with httpx.AsyncClient() as client:
            with pytest.raises(httpx.ConnectError):
                await client.get(f"http://127.0.0.1:{unused_tcp_port}")
