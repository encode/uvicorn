import logging
import socket
import threading
import time
from typing import TYPE_CHECKING, Any, Dict, List, Type

import pytest

from tests.response import Response
from uvicorn import Server
from uvicorn._types import ASGIApplication, ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.config import WS_PROTOCOLS, Config
from uvicorn.lifespan.off import LifespanOff
from uvicorn.lifespan.on import LifespanOn
from uvicorn.main import ServerState
from uvicorn.protocols.http.h11_impl import H11Protocol

try:
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

    skip_if_no_httptools = pytest.mark.skipif(False, reason="httptools is installed")
except ModuleNotFoundError:
    skip_if_no_httptools = pytest.mark.skipif(True, reason="httptools is not installed")

if TYPE_CHECKING:
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


WEBSOCKET_PROTOCOLS = WS_PROTOCOLS.keys()

SIMPLE_GET_REQUEST = b"\r\n".join([b"GET / HTTP/1.1", b"Host: example.org", b"", b""])

SIMPLE_HEAD_REQUEST = b"\r\n".join([b"HEAD / HTTP/1.1", b"Host: example.org", b"", b""])

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

CONNECTION_CLOSE_REQUEST = b"\r\n".join(
    [b"GET / HTTP/1.1", b"Host: example.org", b"Connection: close", b"", b""]
)

LARGE_POST_REQUEST = b"\r\n".join(
    [
        b"POST / HTTP/1.1",
        b"Host: example.org",
        b"Content-Type: text/plain",
        b"Content-Length: 100000",
        b"",
        b"x" * 100000,
    ]
)

START_POST_REQUEST = b"\r\n".join(
    [
        b"POST / HTTP/1.1",
        b"Host: example.org",
        b"Content-Type: application/json",
        b"Content-Length: 18",
        b"",
        b"",
    ]
)

FINISH_POST_REQUEST = b'{"hello": "world"}'

HTTP10_GET_REQUEST = b"\r\n".join([b"GET / HTTP/1.0", b"Host: example.org", b"", b""])

GET_REQUEST_WITH_RAW_PATH = b"\r\n".join(
    [b"GET /one%2Ftwo HTTP/1.1", b"Host: example.org", b"", b""]
)

UPGRADE_REQUEST = b"\r\n".join(
    [
        b"GET / HTTP/1.1",
        b"Host: example.org",
        b"Connection: upgrade",
        b"Upgrade: websocket",
        b"Sec-WebSocket-Version: 11",
        b"",
        b"",
    ]
)

UPGRADE_HTTP2_REQUEST = b"\r\n".join(
    [
        b"GET / HTTP/1.1",
        b"Host: example.org",
        b"Connection: upgrade",
        b"Upgrade: h2c",
        b"Sec-WebSocket-Version: 11",
        b"",
        b"",
    ]
)

INVALID_REQUEST_TEMPLATE = b"\r\n".join(
    [
        b"%s",
        b"Host: example.org",
        b"",
        b"",
    ]
)

GET_REQUEST_HUGE_HEADERS = [
    b"".join(
        [
            b"GET / HTTP/1.1\r\n",
            b"Host: example.org\r\n",
            b"Cookie: " + b"x" * 32 * 1024,
        ]
    ),
    b"".join([b"x" * 32 * 1024 + b"\r\n", b"\r\n", b"\r\n"]),
]


class MockTransport:
    def __init__(self, sockname=None, peername=None, sslcontext=False):
        self.sockname = ("127.0.0.1", 8000) if sockname is None else sockname
        self.peername = ("127.0.0.1", 8001) if peername is None else peername
        self.sslcontext = sslcontext
        self.closed = False
        self.buffer = b""
        self.read_paused = False

    def get_extra_info(self, key):
        return {
            "sockname": self.sockname,
            "peername": self.peername,
            "sslcontext": self.sslcontext,
        }.get(key)

    def write(self, data):
        assert not self.closed
        self.buffer += data

    def close(self):
        assert not self.closed
        self.closed = True

    def pause_reading(self):
        self.read_paused = True

    def resume_reading(self):
        self.read_paused = False

    def is_closing(self):
        return self.closed

    def clear_buffer(self):
        self.buffer = b""

    def set_protocol(self, protocol):
        pass


class MockLoop:
    def __init__(self):
        self._tasks = []
        self._later = []

    def create_task(self, coroutine):
        self._tasks.insert(0, coroutine)
        return MockTask()

    def call_later(self, delay, callback, *args):
        self._later.insert(0, (delay, callback, args))

    async def run_one(self):
        return await self._tasks.pop()

    def run_later(self, with_delay):
        later = []
        for delay, callback, args in self._later:
            if with_delay >= delay:
                callback(*args)
            else:
                later.append((delay, callback, args))
        self._later = later


class MockTask:
    def add_done_callback(self, callback):
        pass


def get_connected_protocol(
    app: ASGIApplication,
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
    lifespan: "LifespanOff | LifespanOn | None" = None,
    **kwargs: Any,
):
    loop = MockLoop()
    transport = MockTransport()
    config = Config(app=app, **kwargs)
    lifespan = lifespan or LifespanOff(config)
    server_state = ServerState()
    protocol = http_protocol_cls(
        config=config,
        server_state=server_state,
        app_state=lifespan.state,
        _loop=loop,  # type: ignore
    )
    protocol.connection_made(transport)  # type: ignore
    return protocol


@pytest.mark.anyio
async def test_get_request(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer


@pytest.mark.anyio
@pytest.mark.parametrize("path", ["/", "/?foo", "/?foo=bar", "/?foo=bar&baz=1"])
async def test_request_logging(
    path, http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]", caplog
):
    get_request_with_query_string = b"\r\n".join(
        ["GET {} HTTP/1.1".format(path).encode("ascii"), b"Host: example.org", b"", b""]
    )
    caplog.set_level(logging.INFO, logger="uvicorn.access")
    logging.getLogger("uvicorn.access").propagate = True

    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls, log_config=None)
    protocol.data_received(get_request_with_query_string)
    await protocol.loop.run_one()
    assert '"GET {} HTTP/1.1" 200'.format(path) in caplog.records[0].message


@pytest.mark.anyio
async def test_head_request(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_HEAD_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" not in protocol.transport.buffer


@pytest.mark.anyio
async def test_post_request(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            assert message["type"] == "http.request"
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        response = Response(b"Body: " + body, media_type="text/plain")
        await response(scope, receive, send)

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_POST_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b'Body: {"hello": "world"}' in protocol.transport.buffer


@pytest.mark.anyio
async def test_keepalive(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    app = Response(b"", status_code=204)

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()

    assert b"HTTP/1.1 204 No Content" in protocol.transport.buffer
    assert not protocol.transport.is_closing()


@pytest.mark.anyio
async def test_keepalive_timeout(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(b"", status_code=204)

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 204 No Content" in protocol.transport.buffer
    assert not protocol.transport.is_closing()
    protocol.loop.run_later(with_delay=1)
    assert not protocol.transport.is_closing()
    protocol.loop.run_later(with_delay=5)
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_close(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    app = Response(b"", status_code=204, headers={"connection": "close"})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 204 No Content" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_chunked_encoding(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(
        b"Hello, world!", status_code=200, headers={"transfer-encoding": "chunked"}
    )

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"0\r\n\r\n" in protocol.transport.buffer
    assert not protocol.transport.is_closing()


@pytest.mark.anyio
async def test_chunked_encoding_empty_body(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(
        b"Hello, world!", status_code=200, headers={"transfer-encoding": "chunked"}
    )

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert protocol.transport.buffer.count(b"0\r\n\r\n") == 1
    assert not protocol.transport.is_closing()


@pytest.mark.anyio
async def test_chunked_encoding_head_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(
        b"Hello, world!", status_code=200, headers={"transfer-encoding": "chunked"}
    )

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_HEAD_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert not protocol.transport.is_closing()


@pytest.mark.anyio
async def test_pipelined_requests(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer
    protocol.transport.clear_buffer()
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer
    protocol.transport.clear_buffer()
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer
    protocol.transport.clear_buffer()


@pytest.mark.anyio
async def test_undersized_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(b"xxx", headers={"content-length": "10"})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_oversized_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(b"xxx" * 20, headers={"content-length": "10"})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_large_post_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(LARGE_POST_REQUEST)
    assert protocol.transport.read_paused
    await protocol.loop.run_one()
    assert not protocol.transport.read_paused


@pytest.mark.anyio
async def test_invalid_http(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(b"x" * 100000)
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_app_exception(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        raise Exception()

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 500 Internal Server Error" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_exception_during_response(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b"1", "more_body": True})
        raise Exception()

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 500 Internal Server Error" not in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_no_response_returned(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        ...

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 500 Internal Server Error" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_partial_response_returned(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        await send({"type": "http.response.start", "status": 200})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 500 Internal Server Error" not in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_duplicate_start_message(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.start", "status": 200})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 500 Internal Server Error" not in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_missing_start_message(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        await send({"type": "http.response.body", "body": b""})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 500 Internal Server Error" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_message_after_body_complete(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b""})
        await send({"type": "http.response.body", "body": b""})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_value_returned(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        await send({"type": "http.response.start", "status": 200})
        await send({"type": "http.response.body", "body": b""})
        return 123

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_early_disconnect(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    got_disconnect_event = False

    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        nonlocal got_disconnect_event

        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break

        got_disconnect_event = True

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_POST_REQUEST)
    protocol.eof_received()
    protocol.connection_lost(None)
    await protocol.loop.run_one()
    assert got_disconnect_event


@pytest.mark.anyio
async def test_early_response(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(START_POST_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    protocol.data_received(FINISH_POST_REQUEST)
    assert not protocol.transport.is_closing()


@pytest.mark.anyio
async def test_read_after_response(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    message_after_response = None

    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        nonlocal message_after_response

        response = Response("Hello, world", media_type="text/plain")
        await response(scope, receive, send)
        message_after_response = await receive()

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_POST_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert message_after_response == {"type": "http.disconnect"}


@pytest.mark.anyio
async def test_http10_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        assert scope["type"] == "http"
        content = "Version: %s" % scope["http_version"]
        response = Response(content, media_type="text/plain")
        await response(scope, receive, send)

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(HTTP10_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Version: 1.0" in protocol.transport.buffer


@pytest.mark.anyio
async def test_root_path(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        assert scope["type"] == "http"
        root_path = scope.get("root_path", "")
        path = scope["path"]
        response = Response(
            f"root_path={root_path} path={path}", media_type="text/plain"
        )
        await response(scope, receive, send)

    protocol = get_connected_protocol(app, http_protocol_cls, root_path="/app")
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"root_path=/app path=/app/" in protocol.transport.buffer


@pytest.mark.anyio
async def test_raw_path(http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]"):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        assert scope["type"] == "http"
        path = scope["path"]
        raw_path = scope.get("raw_path", None)
        assert "/app/one/two" == path
        assert b"/app/one%2Ftwo" == raw_path

        response = Response("Done", media_type="text/plain")
        await response(scope, receive, send)

    protocol = get_connected_protocol(app, http_protocol_cls, root_path="/app")
    protocol.data_received(GET_REQUEST_WITH_RAW_PATH)
    await protocol.loop.run_one()
    assert b"Done" in protocol.transport.buffer


@pytest.mark.anyio
async def test_max_concurrency(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls, limit_concurrency=1)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 503 Service Unavailable" in protocol.transport.buffer


@pytest.mark.anyio
async def test_shutdown_during_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(b"", status_code=204)

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    protocol.shutdown()
    await protocol.loop.run_one()
    assert b"HTTP/1.1 204 No Content" in protocol.transport.buffer
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_shutdown_during_idle(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.shutdown()
    assert protocol.transport.buffer == b""
    assert protocol.transport.is_closing()


@pytest.mark.anyio
async def test_100_continue_sent_when_body_consumed(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        body = b""
        more_body = True
        while more_body:
            message = await receive()
            assert message["type"] == "http.request"
            body += message.get("body", b"")
            more_body = message.get("more_body", False)
        response = Response(b"Body: " + body, media_type="text/plain")
        await response(scope, receive, send)

    protocol = get_connected_protocol(app, http_protocol_cls)
    EXPECT_100_REQUEST = b"\r\n".join(
        [
            b"POST / HTTP/1.1",
            b"Host: example.org",
            b"Expect: 100-continue",
            b"Content-Type: application/json",
            b"Content-Length: 18",
            b"",
            b'{"hello": "world"}',
        ]
    )
    protocol.data_received(EXPECT_100_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 100 Continue" in protocol.transport.buffer
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b'Body: {"hello": "world"}' in protocol.transport.buffer


@pytest.mark.anyio
async def test_100_continue_not_sent_when_body_not_consumed(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response(b"", status_code=204)

    protocol = get_connected_protocol(app, http_protocol_cls)
    EXPECT_100_REQUEST = b"\r\n".join(
        [
            b"POST / HTTP/1.1",
            b"Host: example.org",
            b"Expect: 100-continue",
            b"Content-Type: application/json",
            b"Content-Length: 18",
            b"",
            b'{"hello": "world"}',
        ]
    )
    protocol.data_received(EXPECT_100_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 100 Continue" not in protocol.transport.buffer
    assert b"HTTP/1.1 204 No Content" in protocol.transport.buffer


@pytest.mark.anyio
async def test_supported_upgrade_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    pytest.importorskip("wsproto")

    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls, ws="wsproto")
    protocol.data_received(UPGRADE_REQUEST)
    assert b"HTTP/1.1 426 " in protocol.transport.buffer


@pytest.mark.anyio
async def test_unsupported_ws_upgrade_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls, ws="none")
    protocol.data_received(UPGRADE_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer


@pytest.mark.anyio
async def test_unsupported_ws_upgrade_request_warn_on_auto(
    caplog: pytest.LogCaptureFixture,
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls, ws="auto")
    protocol.ws_protocol_class = None
    protocol.data_received(UPGRADE_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer
    warnings = [
        record.msg
        for record in filter(
            lambda record: record.levelname == "WARNING", caplog.records
        )
    ]
    assert "Unsupported upgrade request." in warnings
    msg = "No supported WebSocket library detected. Please use \"pip install 'uvicorn[standard]'\", or install 'websockets' or 'wsproto' manually."  # noqa: E501
    assert msg in warnings


@pytest.mark.anyio
async def test_http2_upgrade_request(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
    ws_protocol_cls: "Type[WebSocketProtocol | WSProtocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls, ws=ws_protocol_cls)
    protocol.data_received(UPGRADE_HTTP2_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer


async def asgi3app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
    pass


def asgi2app(scope: Scope):
    async def asgi(receive: ASGIReceiveCallable, send: ASGISendCallable):
        pass

    return asgi


@pytest.mark.anyio
@pytest.mark.parametrize(
    "asgi2or3_app, expected_scopes",
    [
        (asgi3app, {"version": "3.0", "spec_version": "2.3"}),
        (asgi2app, {"version": "2.0", "spec_version": "2.3"}),
    ],
)
async def test_scopes(
    asgi2or3_app: ASGIApplication,
    expected_scopes: Dict[str, str],
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    protocol = get_connected_protocol(asgi2or3_app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert expected_scopes == protocol.scope.get("asgi")


@pytest.mark.anyio
@pytest.mark.parametrize(
    "request_line",
    [
        pytest.param(b"G?T / HTTP/1.1", id="invalid-method"),
        pytest.param(b"GET /?x=y z HTTP/1.1", id="invalid-path"),
        pytest.param(b"GET / HTTP1.1", id="invalid-http-version"),
    ],
)
async def test_invalid_http_request(
    request_line, http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]", caplog
):
    app = Response("Hello, world", media_type="text/plain")
    request = INVALID_REQUEST_TEMPLATE % request_line

    caplog.set_level(logging.INFO, logger="uvicorn.error")
    logging.getLogger("uvicorn.error").propagate = True

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(request)
    assert b"HTTP/1.1 400 Bad Request" in protocol.transport.buffer
    assert b"Invalid HTTP request received." in protocol.transport.buffer


@skip_if_no_httptools
def test_fragmentation(unused_tcp_port: int):
    def receive_all(sock: socket.socket):
        chunks: List[bytes] = []
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)

    app = Response("Hello, world", media_type="text/plain")

    def send_fragmented_req(path: str):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("127.0.0.1", unused_tcp_port))
        d = (
            f"GET {path} HTTP/1.1\r\n" "Host: localhost\r\n" "Connection: close\r\n\r\n"
        ).encode()
        split = len(path) // 2
        sock.sendall(d[:split])
        time.sleep(0.01)
        sock.sendall(d[split:])
        resp = receive_all(sock)
        # see https://github.com/kmonsoor/py-amqplib/issues/45
        # we skip the error on bsd systems if python is too slow
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except Exception:  # pragma: no cover
            pass
        sock.close()
        return resp

    config = Config(app=app, http="httptools", port=unused_tcp_port)
    server = Server(config=config)
    t = threading.Thread(target=server.run)
    t.daemon = True
    t.start()
    time.sleep(1)  # wait for uvicorn to start

    path = "/?param=" + "q" * 10
    response = send_fragmented_req(path)
    bad_response = b"HTTP/1.1 400 Bad Request"
    assert bad_response != response[: len(bad_response)]
    server.should_exit = True
    t.join()


@pytest.mark.anyio
async def test_huge_headers_h11protocol_failure():
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, H11Protocol)
    # Huge headers make h11 fail in it's default config
    # h11 sends back a 400 in this case
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[0])
    assert b"HTTP/1.1 400 Bad Request" in protocol.transport.buffer
    assert b"Connection: close" in protocol.transport.buffer
    assert b"Invalid HTTP request received." in protocol.transport.buffer


@pytest.mark.anyio
@skip_if_no_httptools
async def test_huge_headers_httptools_will_pass():
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, HttpToolsProtocol)
    # Huge headers make h11 fail in it's default config
    # httptools protocol will always pass
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[0])
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[1])
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer


@pytest.mark.anyio
async def test_huge_headers_h11protocol_failure_with_setting():
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(
        app, H11Protocol, h11_max_incomplete_event_size=20 * 1024
    )
    # Huge headers make h11 fail in it's default config
    # h11 sends back a 400 in this case
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[0])
    assert b"HTTP/1.1 400 Bad Request" in protocol.transport.buffer
    assert b"Connection: close" in protocol.transport.buffer
    assert b"Invalid HTTP request received." in protocol.transport.buffer


@pytest.mark.anyio
@skip_if_no_httptools
async def test_huge_headers_httptools():
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, HttpToolsProtocol)
    # Huge headers make h11 fail in it's default config
    # httptools protocol will always pass
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[0])
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[1])
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer


@pytest.mark.anyio
async def test_huge_headers_h11_max_incomplete():
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(
        app, H11Protocol, h11_max_incomplete_event_size=64 * 1024
    )
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[0])
    protocol.data_received(GET_REQUEST_HUGE_HEADERS[1])
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"Hello, world" in protocol.transport.buffer


@pytest.mark.anyio
async def test_return_close_header(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    app = Response("Hello, world", media_type="text/plain")

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(CONNECTION_CLOSE_REQUEST)
    await protocol.loop.run_one()
    assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
    assert b"content-type: text/plain" in protocol.transport.buffer
    assert b"content-length: 12" in protocol.transport.buffer
    # NOTE: We need to use `.lower()` because H11 implementation doesn't allow Uvicorn
    # to lowercase them. See: https://github.com/python-hyper/h11/issues/156
    assert b"connection: close" in protocol.transport.buffer.lower()


@pytest.mark.anyio
async def test_iterator_headers(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        headers = iter([(b"x-test-header", b"test value")])
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": b""})

    protocol = get_connected_protocol(app, http_protocol_cls)
    protocol.data_received(SIMPLE_GET_REQUEST)
    await protocol.loop.run_one()
    assert b"x-test-header: test value" in protocol.transport.buffer


@pytest.mark.anyio
async def test_lifespan_state(
    http_protocol_cls: "Type[HttpToolsProtocol | H11Protocol]",
):
    expected_states = [{"a": 123, "b": [1]}, {"a": 123, "b": [1, 2]}]

    async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable):
        assert "state" in scope
        expected_state = expected_states.pop(0)
        assert scope["state"] == expected_state
        # modifications to keys are not preserved
        scope["state"]["a"] = 456
        # unless of course the value itself is mutated
        scope["state"]["b"].append(2)
        return await Response("Hi!")(scope, receive, send)

    lifespan = LifespanOn(config=Config(app=app))
    # skip over actually running the lifespan, that is tested
    # in the lifespan tests
    lifespan.state.update({"a": 123, "b": [1]})

    protocol = get_connected_protocol(app, http_protocol_cls, lifespan=lifespan)
    for _ in range(2):
        protocol.data_received(SIMPLE_GET_REQUEST)
        await protocol.loop.run_one()
        assert b"HTTP/1.1 200 OK" in protocol.transport.buffer
        assert b"Hi!" in protocol.transport.buffer

    assert not expected_states  # consumed
