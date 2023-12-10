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

if typing.TYPE_CHECKING:
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


@contextlib.contextmanager
def caplog_for_logger(caplog, logger_name):
    logger = logging.getLogger(logger_name)
    logger.propagate, old_propagate = False, logger.propagate
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)
        logger.propagate = old_propagate


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.anyio
async def test_trace_logging(caplog, logging_config, unused_tcp_port: int):
    config = Config(
        app=app,
        log_level="trace",
        log_config=logging_config,
        lifespan="auto",
        port=unused_tcp_port,
    )
    with caplog_for_logger(caplog, "uvicorn.asgi"):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
        assert response.status_code == 204
        messages = [
            record.message for record in caplog.records if record.name == "uvicorn.asgi"
        ]
        assert "ASGI [1] Started scope=" in messages.pop(0)
        assert "ASGI [1] Raised exception" in messages.pop(0)
        assert "ASGI [2] Started scope=" in messages.pop(0)
        assert "ASGI [2] Send " in messages.pop(0)
        assert "ASGI [2] Send " in messages.pop(0)
        assert "ASGI [2] Completed" in messages.pop(0)


@pytest.mark.anyio
async def test_trace_logging_on_http_protocol(
    http_protocol_cls, caplog, logging_config, unused_tcp_port: int
):
    config = Config(
        app=app,
        log_level="trace",
        http=http_protocol_cls,
        log_config=logging_config,
        port=unused_tcp_port,
    )
    with caplog_for_logger(caplog, "uvicorn.error"):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
        assert response.status_code == 204
        messages = [
            record.message
            for record in caplog.records
            if record.name == "uvicorn.error"
        ]
        assert any(" - HTTP connection made" in message for message in messages)
        assert any(" - HTTP connection lost" in message for message in messages)


@pytest.mark.anyio
async def test_trace_logging_on_ws_protocol(
    ws_protocol_cls: "typing.Type[WSProtocol | WebSocketProtocol]",
    caplog,
    logging_config,
    unused_tcp_port: int,
):
    async def websocket_app(scope, receive, send):
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
        ws=ws_protocol_cls,
        port=unused_tcp_port,
    )
    with caplog_for_logger(caplog, "uvicorn.error"):
        async with run_server(config):
            is_open = await open_connection(f"ws://127.0.0.1:{unused_tcp_port}")
        assert is_open
        messages = [
            record.message
            for record in caplog.records
            if record.name == "uvicorn.error"
        ]
        assert any(" - Upgrading to WebSocket" in message for message in messages)
        assert any(" - WebSocket connection made" in message for message in messages)
        assert any(" - WebSocket connection lost" in message for message in messages)


@pytest.mark.anyio
@pytest.mark.parametrize("use_colors", [(True), (False), (None)])
async def test_access_logging(use_colors, caplog, logging_config, unused_tcp_port: int):
    config = Config(
        app=app, use_colors=use_colors, log_config=logging_config, port=unused_tcp_port
    )
    with caplog_for_logger(caplog, "uvicorn.access"):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")

        assert response.status_code == 204
        messages = [
            record.message
            for record in caplog.records
            if record.name == "uvicorn.access"
        ]
        assert '"GET / HTTP/1.1" 204' in messages.pop()


@pytest.mark.anyio
@pytest.mark.parametrize("use_colors", [(True), (False)])
async def test_default_logging(
    use_colors, caplog, logging_config, unused_tcp_port: int
):
    config = Config(
        app=app, use_colors=use_colors, log_config=logging_config, port=unused_tcp_port
    )
    with caplog_for_logger(caplog, "uvicorn.access"):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")
        assert response.status_code == 204
        messages = [
            record.message for record in caplog.records if "uvicorn" in record.name
        ]
        assert "Started server process" in messages.pop(0)
        assert "Waiting for application startup" in messages.pop(0)
        assert "ASGI 'lifespan' protocol appears unsupported" in messages.pop(0)
        assert "Application startup complete" in messages.pop(0)
        assert "Uvicorn running on http://127.0.0.1" in messages.pop(0)
        assert '"GET / HTTP/1.1" 204' in messages.pop(0)
        assert "Shutting down" in messages.pop(0)


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like system")
async def test_running_log_using_uds(
    caplog, short_socket_name, unused_tcp_port: int
):  # pragma: py-win32
    config = Config(app=app, uds=short_socket_name, port=unused_tcp_port)
    with caplog_for_logger(caplog, "uvicorn.access"):
        async with run_server(config):
            ...

    messages = [record.message for record in caplog.records if "uvicorn" in record.name]
    assert (
        f"Uvicorn running on unix socket {short_socket_name} (Press CTRL+C to quit)"
        in messages
    )


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like system")
async def test_running_log_using_fd(caplog, unused_tcp_port: int):  # pragma: py-win32
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        fd = sock.fileno()
        config = Config(app=app, fd=fd, port=unused_tcp_port)
        with caplog_for_logger(caplog, "uvicorn.access"):
            async with run_server(config):
                ...
        sockname = sock.getsockname()
    messages = [record.message for record in caplog.records if "uvicorn" in record.name]
    assert f"Uvicorn running on socket {sockname} (Press CTRL+C to quit)" in messages


@pytest.mark.anyio
async def test_unknown_status_code(caplog, unused_tcp_port: int):
    async def app(scope, receive, send):
        assert scope["type"] == "http"
        await send({"type": "http.response.start", "status": 599, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    config = Config(app=app, port=unused_tcp_port)
    with caplog_for_logger(caplog, "uvicorn.access"):
        async with run_server(config):
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{unused_tcp_port}")

        assert response.status_code == 599
        messages = [
            record.message
            for record in caplog.records
            if record.name == "uvicorn.access"
        ]
        assert '"GET / HTTP/1.1" 599' in messages.pop()


@pytest.mark.anyio
async def test_server_start_with_port_zero(caplog: pytest.LogCaptureFixture):
    config = Config(app=app, port=0)
    async with run_server(config) as server:
        server = server.servers[0]
        sock = server.sockets[0]
        host, port = sock.getsockname()
    messages = [record.message for record in caplog.records if "uvicorn" in record.name]
    assert f"Uvicorn running on http://{host}:{port} (Press CTRL+C to quit)" in messages
