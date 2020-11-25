import asyncio
import contextlib
import logging
from typing import Any, Callable, Tuple

import pytest

from uvicorn._handlers.concurrency import AsyncioSocket
from uvicorn._handlers.http11 import handle_http11
from uvicorn.config import Config
from uvicorn.server import ServerState

from ..response import Response

SIMPLE_GET_REQUEST = b"\r\n".join(
    [
        b"GET / HTTP/1.1",
        b"Host: example.org",
        b"",
        b"",
    ]
)

SIMPLE_HEAD_REQUEST = b"\r\n".join(
    [
        b"HEAD / HTTP/1.1",
        b"Host: example.org",
        b"",
        b"",
    ]
)

SIMPLE_POST_REQUEST = b"\r\n".join(
    [
        b"POST / HTTP/1.1",
        b"Host: example.org",
        b"Content-Type: application/json",
        b"Content-Length: 18",
        b"",
        b'{"hello": "world"}',
    ]
)

HTTP11_IMPLEMENTATIONS = ["h11"]

try:
    import httptools  # noqa: F401
except ImportError:
    pass
else:
    HTTP11_IMPLEMENTATIONS.append("httptools")


class MockSocket(AsyncioSocket):
    """
    An in-memory socket for testing purposes.
    """

    def __init__(self, request: bytes, prevent_keepalive_loop: bool = True) -> None:
        self._request = request
        self._prevent_keepalive_loop = prevent_keepalive_loop
        self._response = b""
        self._response_received = asyncio.Event()
        self._readable = asyncio.Event()
        self._is_closed = False

    def get_remote_addr(self) -> Tuple[str, int]:
        return ("127.0.0.1", 8000)

    def get_local_addr(self) -> Tuple[str, int]:
        return ("127.0.0.1", 42424)

    is_ssl = False

    @property
    def response(self) -> bytes:
        return self._response

    async def read(self, n: int) -> bytes:
        if self._readable.is_set():
            return b""

        if not self._request:
            await self._readable.wait()
            return b""

        data, self._request = self._request[:n], self._request[n:]

        if not self._request and self._prevent_keepalive_loop:
            self._response_received.set()
            self._readable.set()

        return data

    async def write(self, data: bytes) -> None:
        if data == b"":
            self._response_received.set()
            if self._prevent_keepalive_loop:
                # Simulate a client disconnect right after having received
                # the response so that the HTTP handler doesn't run a keep-alive
                # cycle for nothing.
                self.simulate_client_disconnect()
            return

        self._response += data

    async def wait_response_received(self) -> None:
        await self._response_received.wait()

    def simulate_client_disconnect(self) -> None:
        self._readable.set()

    def send_eof(self) -> None:
        # Simulate instantaneous acknowledgement by client.
        self._readable.set()

    async def aclose(self) -> None:
        self._is_closed = True

    @property
    def is_closed(self) -> bool:
        return self._is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_get_request(http: str) -> None:
    app = Response("Hello, world", media_type="text/plain")
    sock = MockSocket(SIMPLE_GET_REQUEST)

    await handle_http11(sock, ServerState(), Config(app=app, http=http))

    assert b"HTTP/1.1 200 OK" in sock.response
    assert b"Hello, world" in sock.response


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_head_request(http: str) -> None:
    app = Response("Hello, world", media_type="text/plain")
    sock = MockSocket(SIMPLE_HEAD_REQUEST)

    await handle_http11(sock, ServerState(), Config(app=app, http=http))

    assert b"HTTP/1.1 200 OK" in sock.response
    assert b"Hello, world" not in sock.response


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_post_request(http: str) -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        response = Response(b"Body: " + body, media_type="text/plain")
        await response(scope, receive, send)

    sock = MockSocket(SIMPLE_POST_REQUEST)

    await handle_http11(sock, ServerState(), Config(app=app, http=http))

    assert b"HTTP/1.1 200 OK" in sock.response
    assert b'Body: {"hello": "world"}' in sock.response


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
@pytest.mark.parametrize("path", ["/", "/?foo", "/?foo=bar", "/?foo=bar&baz=1"])
async def test_request_logging(http: str, path: str, caplog: Any) -> None:
    app = Response("Hello, world", media_type="text/plain")
    get_request_with_query_string = b"\r\n".join(
        ["GET {} HTTP/1.1".format(path).encode("ascii"), b"Host: example.org", b"", b""]
    )

    sock = MockSocket(get_request_with_query_string)
    state = ServerState()
    config = Config(app=app, http=http)  # Configures initial logging.

    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        logging.getLogger("uvicorn.access").propagate = True
        await handle_http11(sock, state, config)

    assert '"GET {} HTTP/1.1" 200'.format(path) in caplog.records[0].message


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_keepalive(http: str) -> None:
    app = Response(b"", status_code=204)
    sock = MockSocket(SIMPLE_GET_REQUEST, prevent_keepalive_loop=False)

    config = Config(app=app, http=http)

    loop = asyncio.get_event_loop()
    task = loop.create_task(handle_http11(sock, ServerState(), config))
    try:
        await sock.wait_response_received()

        assert b"HTTP/1.1 204 No Content" in sock.response
        assert not sock.is_closed

        sock.simulate_client_disconnect()
    except Exception:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        raise

    await task
    assert sock.is_closed


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_keepalive_timeout(http: str) -> None:
    app = Response(b"", status_code=204)
    sock = MockSocket(SIMPLE_GET_REQUEST, prevent_keepalive_loop=False)

    config = Config(app=app, http=http, timeout_keep_alive=0.05)

    loop = asyncio.get_event_loop()
    task = loop.create_task(handle_http11(sock, ServerState(), config))
    try:
        await sock.wait_response_received()
        assert b"HTTP/1.1 204 No Content" in sock.response
        assert not sock.is_closed

        await asyncio.sleep(0.01)
        assert not sock.is_closed

        await asyncio.sleep(0.1)
        assert sock.is_closed
    except Exception:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        raise
    else:
        await task


@pytest.mark.asyncio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_close(http: str) -> None:
    app = Response(b"", status_code=204, headers={"connection": "close"})
    sock = MockSocket(SIMPLE_GET_REQUEST, prevent_keepalive_loop=False)

    await handle_http11(sock, ServerState(), Config(app=app, http=http))

    assert b"HTTP/1.1 204 No Content" in sock.response
    assert sock.is_closed
