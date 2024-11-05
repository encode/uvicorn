from __future__ import annotations

import contextlib
import logging
import socket
import sys
import typing

import httpx
import pytest
import websockets
import websockets.client

from tests.utils import run_server
from uvicorn import Config
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope

if typing.TYPE_CHECKING:
    import sys

    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol as _WSProtocol

    if sys.version_info >= (3, 10):  # pragma: no cover
        from typing import TypeAlias
    else:  # pragma: no cover
        from typing_extensions import TypeAlias

    WSProtocol: TypeAlias = "type[WebSocketProtocol | _WSProtocol]"

pytestmark = pytest.mark.anyio
my_logger_mappings = {
    "general": "mylogger.general",
    "access": "mylogger.access",
    "asgi": "mylogger.asgi",
}


@contextlib.contextmanager
def caplog_for_logger(caplog: pytest.LogCaptureFixture, logger_name: str) -> typing.Iterator[pytest.LogCaptureFixture]:
    logger = logging.getLogger(logger_name)
    logger.propagate, old_propagate = False, logger.propagate
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)
        logger.propagate = old_propagate


async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_trace_logging(caplog: pytest.LogCaptureFixture, logging_config, unused_tcp_port: int, logger_mappings):
    config = Config(
        app=app,
        log_level="trace",
        log_config=logging_config,
        logger_mappings=logger_mappings,
        lifespan="auto",
        port=unused_tcp_port,
    )
    logger_name = config.get_logger_name("asgi")
    with caplog_for_logger(caplog, logger_name):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
        assert response.status_code == 204
        messages = [record.message for record in caplog.records if record.name == logger_name]
        assert "ASGI [1] Started scope=" in messages.pop(0)
        assert "ASGI [1] Raised exception" in messages.pop(0)
        assert "ASGI [2] Started scope=" in messages.pop(0)
        assert "ASGI [2] Send " in messages.pop(0)
        assert "ASGI [2] Send " in messages.pop(0)
        assert "ASGI [2] Completed" in messages.pop(0)


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_trace_logging_on_http_protocol(
    http_protocol_cls,
    caplog,
    logging_config,
    unused_tcp_port: int,
    logger_mappings,
):
    config = Config(
        app=app,
        log_level="trace",
        http=http_protocol_cls,
        log_config=logging_config,
        logger_mappings=logger_mappings,
        port=unused_tcp_port,
    )
    logger_name = config.get_logger_name("general")
    with caplog_for_logger(caplog, logger_name):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
        assert response.status_code == 204
        messages = [record.message for record in caplog.records if record.name == logger_name]
        assert any(" - HTTP connection made" in message for message in messages)
        assert any(" - HTTP connection lost" in message for message in messages)


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_trace_logging_on_ws_protocol(
    ws_protocol_cls: WSProtocol,
    caplog,
    logging_config,
    unused_tcp_port: int,
    logger_mappings,
):
    async def websocket_app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        assert scope["type"] == "websocket"
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.disconnect":
                break

    async def open_connection(url):
        async with websockets.client.connect(url) as websocket:
            return websocket.open

    config = Config(
        app=websocket_app,
        log_level="trace",
        log_config=logging_config,
        logger_mappings=logger_mappings,
        ws=ws_protocol_cls,
        port=unused_tcp_port,
    )
    logger_name = config.get_logger_name("general")
    with caplog_for_logger(caplog, logger_name):
        async with run_server(config):
            is_open = await open_connection(f"ws://127.0.0.1:{unused_tcp_port}")
        assert is_open
        messages = [record.message for record in caplog.records if record.name == logger_name]
        assert any(" - Upgrading to WebSocket" in message for message in messages)
        assert any(" - WebSocket connection made" in message for message in messages)
        assert any(" - WebSocket connection lost" in message for message in messages)


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
@pytest.mark.parametrize("use_colors", [(True), (False), (None)])
async def test_access_logging(
    use_colors: bool,
    caplog: pytest.LogCaptureFixture,
    logging_config,
    unused_tcp_port: int,
    logger_mappings,
):
    config = Config(
        app=app,
        use_colors=use_colors,
        log_config=logging_config,
        logger_mappings=logger_mappings,
        port=unused_tcp_port,
    )
    logger_name = config.get_logger_name("access")
    with caplog_for_logger(caplog, logger_name):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")

        assert response.status_code == 204
        messages = [record.message for record in caplog.records if record.name == logger_name]
        assert '"GET / HTTP/1.1" 204' in messages.pop()


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
@pytest.mark.parametrize("use_colors", [(True), (False)])
async def test_default_logging(
    use_colors: bool,
    caplog: pytest.LogCaptureFixture,
    logging_config,
    unused_tcp_port: int,
    logger_mappings,
):
    config = Config(
        app=app,
        use_colors=use_colors,
        log_config=logging_config,
        logger_mappings=logger_mappings,
        port=unused_tcp_port,
    )
    main_logger_name = config.get_logger_name("main")
    logger_name = config.get_logger_name("access")
    with caplog_for_logger(caplog, logger_name):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
        assert response.status_code == 204
        messages = [record.message for record in caplog.records if main_logger_name in record.name]
        assert "Started server process" in messages.pop(0)
        assert "Waiting for application startup" in messages.pop(0)
        assert "ASGI 'lifespan' protocol appears unsupported" in messages.pop(0)
        assert "Application startup complete" in messages.pop(0)
        assert "Uvicorn running on http://127.0.0.1" in messages.pop(0)
        assert '"GET / HTTP/1.1" 204' in messages.pop(0)
        assert "Shutting down" in messages.pop(0)


@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like system")
@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_running_log_using_uds(
    caplog: pytest.LogCaptureFixture,
    short_socket_name: str,
    unused_tcp_port: int,
    logger_mappings,
):  # pragma: py-win32
    config = Config(
        app=app,
        uds=short_socket_name,
        port=unused_tcp_port,
        logger_mappings=logger_mappings,
    )
    with caplog_for_logger(caplog, config.get_logger_name("access")):
        async with run_server(config):
            ...

    messages = [record.message for record in caplog.records if config.get_logger_name("main") in record.name]
    assert f"Uvicorn running on unix socket {short_socket_name} (Press CTRL+C to quit)" in messages


@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like system")
@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_running_log_using_fd(
    caplog: pytest.LogCaptureFixture,
    unused_tcp_port: int,
    logger_mappings,
):  # pragma: py-win32
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        fd = sock.fileno()
        config = Config(
            app=app,
            fd=fd,
            port=unused_tcp_port,
            logger_mappings=logger_mappings,
        )
        with caplog_for_logger(caplog, config.get_logger_name("access")):
            async with run_server(config):
                ...
        sockname = sock.getsockname()
    messages = [record.message for record in caplog.records if config.get_logger_name("main") in record.name]
    assert f"Uvicorn running on socket {sockname} (Press CTRL+C to quit)" in messages


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_unknown_status_code(
    caplog: pytest.LogCaptureFixture,
    unused_tcp_port: int,
    logger_mappings,
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        assert scope["type"] == "http"
        await send({"type": "http.response.start", "status": 599, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    config = Config(
        app=app,
        port=unused_tcp_port,
        logger_mappings=logger_mappings,
    )
    logger_name = config.get_logger_name("access")
    with caplog_for_logger(caplog, logger_name):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")

        assert response.status_code == 599
        messages = [record.message for record in caplog.records if record.name == logger_name]
        assert '"GET / HTTP/1.1" 599' in messages.pop()


@pytest.mark.parametrize("logger_mappings", [None, my_logger_mappings])
async def test_server_start_with_port_zero(
    caplog: pytest.LogCaptureFixture,
    logger_mappings,
):
    config = Config(
        app=app,
        port=0,
        logger_mappings=logger_mappings,
    )
    logger_name = config.get_logger_name("main")
    async with run_server(config) as _server:
        server = _server.servers[0]
        sock = server.sockets[0]
        host, port = sock.getsockname()
    messages = [record.message for record in caplog.records if logger_name in record.name]
    assert f"Uvicorn running on http://{host}:{port} (Press CTRL+C to quit)" in messages
