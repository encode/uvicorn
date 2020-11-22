import logging
from typing import Any, Callable, Tuple

import pytest

from uvicorn._async_agnostic.backends.auto import AutoBackend
from uvicorn._async_agnostic.backends.base import AsyncSocket
from uvicorn._async_agnostic.http11.handler import handle_http11
from uvicorn._async_agnostic.state import ServerState
from uvicorn.config import Config

from ..response import Response
from .utils import HTTP11_IMPLEMENTATIONS

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


class MockSocket(AsyncSocket):
    """
    An in-memory socket for testing purposes.
    """

    def __init__(self, request: bytes, prevent_keepalive_loop: bool = True) -> None:
        self._backend = AutoBackend()
        self._request = request
        self._prevent_keepalive_loop = prevent_keepalive_loop
        self._response = b""
        self._readable = False
        self._is_closed = False
        self._response_received = self._backend.create_event()

    def get_remote_addr(self) -> Tuple[str, int]:
        return ("127.0.0.1", 8000)

    def get_local_addr(self) -> Tuple[str, int]:
        return ("127.0.0.1", 42424)

    is_ssl = False

    @property
    def response(self) -> bytes:
        return self._response

    async def read(self, n: int) -> bytes:
        if self._readable:
            return b""

        if not self._request:
            while not self._readable:
                await self._backend.sleep(0.01)
            return b""

        data, self._request = self._request[:n], self._request[n:]

        if not self._request and self._prevent_keepalive_loop:
            await self._response_received.set()
            self._readable = True

        return data

    async def write(self, data: bytes) -> None:
        if data == b"":
            await self._response_received.set()
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
        self._readable = True

    async def send_eof(self) -> None:
        # Simulate instantaneous acknowledgement by client.
        self._readable = True

    async def aclose(self) -> None:
        self._is_closed = True

    @property
    def is_closed(self) -> bool:
        return self._is_closed


@pytest.mark.anyio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_get_request(http: str) -> None:
    app = Response("Hello, world", media_type="text/plain")
    sock = MockSocket(SIMPLE_GET_REQUEST)

    await handle_http11(sock, ServerState(), Config(app=app, http=http))

    assert b"HTTP/1.1 200 OK" in sock.response
    assert b"Hello, world" in sock.response


@pytest.mark.anyio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_head_request(http: str) -> None:
    app = Response("Hello, world", media_type="text/plain")
    sock = MockSocket(SIMPLE_HEAD_REQUEST)

    await handle_http11(sock, ServerState(), Config(app=app, http=http))

    assert b"HTTP/1.1 200 OK" in sock.response
    assert b"Hello, world" not in sock.response


@pytest.mark.anyio
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


@pytest.mark.anyio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
@pytest.mark.parametrize("path", ["/", "/?foo", "/?foo=bar", "/?foo=bar&baz=1"])
async def test_request_logging(http: str, path: str, caplog: Any) -> None:
    app = Response("Hello, world", media_type="text/plain")
    get_request_with_query_string = b"\r\n".join(
        [
            "GET {} HTTP/1.1".format(path).encode("ascii"),
            b"Host: example.org",
            b"",
            b"",
        ]
    )

    sock = MockSocket(get_request_with_query_string)
    state = ServerState()
    config = Config(app=app, http=http)  # Keep this here -- configures initial logging.

    with caplog.at_level(logging.INFO, logger="uvicorn.access"):
        logging.getLogger("uvicorn.access").propagate = True
        await handle_http11(sock, state, config)

    assert '"GET {} HTTP/1.1" 200'.format(path) in caplog.records[0].message


@pytest.mark.anyio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_keepalive(http: str) -> None:
    app = Response(b"", status_code=204)
    sock = MockSocket(SIMPLE_GET_REQUEST, prevent_keepalive_loop=False)

    config = Config(app=app, http=http)

    async with AutoBackend().start_soon(handle_http11, sock, ServerState(), config):
        await sock.wait_response_received()
        assert b"HTTP/1.1 204 No Content" in sock.response
        assert not sock.is_closed
        sock.simulate_client_disconnect()

    assert sock.is_closed


@pytest.mark.anyio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_keepalive_timeout(http: str) -> None:
    app = Response(b"", status_code=204)
    sock = MockSocket(SIMPLE_GET_REQUEST, prevent_keepalive_loop=False)

    backend = AutoBackend()
    config = Config(app=app, http=http, timeout_keep_alive=0.1)

    async with backend.start_soon(handle_http11, sock, ServerState(), config):
        await sock.wait_response_received()
        assert b"HTTP/1.1 204 No Content" in sock.response
        assert not sock.is_closed

        await backend.sleep(0.01)
        assert not sock.is_closed

        await backend.sleep(0.2)
        assert sock.is_closed


@pytest.mark.anyio
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
async def test_close(http: str) -> None:
    app = Response(b"", status_code=204, headers={"connection": "close"})
    sock = MockSocket(SIMPLE_GET_REQUEST, prevent_keepalive_loop=False)

    await handle_http11(sock, state=ServerState(), config=Config(app=app, http=http))

    assert b"HTTP/1.1 204 No Content" in sock.response
    assert sock.is_closed
