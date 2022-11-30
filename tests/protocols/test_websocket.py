import asyncio

import httpx
import pytest

from tests.protocols.test_http import HTTP_PROTOCOLS
from tests.utils import run_server
from uvicorn.config import Config
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

try:
    import websockets
    import websockets.client
    import websockets.exceptions
    from websockets.extensions.permessage_deflate import ClientPerMessageDeflateFactory

    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
except ImportError:  # pragma: nocover
    websockets = None
    WebSocketProtocol = None
    ClientPerMessageDeflateFactory = None

ONLY_WEBSOCKETPROTOCOL = [p for p in [WebSocketProtocol] if p is not None]
ONLY_WS_PROTOCOL = [p for p in [WSProtocol] if p is not None]
WS_PROTOCOLS = [p for p in [WSProtocol, WebSocketProtocol] if p is not None]
pytestmark = pytest.mark.skipif(
    websockets is None, reason="This test needs the websockets module"
)


class WebSocketResponse:
    def __init__(self, scope, receive, send):
        self.scope = scope
        self.receive = receive
        self.send = send

    def __await__(self):
        return self.asgi().__await__()

    async def asgi(self):
        while True:
            message = await self.receive()
            message_type = message["type"].replace(".", "_")
            handler = getattr(self, message_type, None)
            if handler is not None:
                await handler(message)
            if message_type == "websocket_disconnect":
                break


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_invalid_upgrade(ws_protocol_cls, http_protocol_cls):
    def app(scope):
        return None

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:8000",
                headers={
                    "upgrade": "websocket",
                    "connection": "upgrade",
                    "sec-webSocket-version": "11",
                },
            )
        if response.status_code == 426:
            # response.text == ""
            pass  # ok, wsproto 0.13
        else:
            assert response.status_code == 400
            assert response.text.lower().strip().rstrip(".") in [
                "missing sec-websocket-key header",
                "missing sec-websocket-version header",  # websockets
                "missing or empty sec-websocket-key header",  # wsproto
                "failed to open a websocket connection: missing "
                "sec-websocket-key header",
                "failed to open a websocket connection: missing or empty "
                "sec-websocket-key header",
            ]


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_accept_connection(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000")
        assert is_open


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_supports_permessage_deflate_extension(
    ws_protocol_cls, http_protocol_cls
):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        extension_factories = [ClientPerMessageDeflateFactory()]
        async with websockets.connect(url, extensions=extension_factories) as websocket:
            return [extension.name for extension in websocket.extensions]

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        extension_names = await open_connection("ws://127.0.0.1:8000")
        assert "permessage-deflate" in extension_names


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_can_disable_permessage_deflate_extension(
    ws_protocol_cls, http_protocol_cls
):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        # enable per-message deflate on the client, so that we can check the server
        # won't support it when it's disabled.
        extension_factories = [ClientPerMessageDeflateFactory()]
        async with websockets.connect(url, extensions=extension_factories) as websocket:
            return [extension.name for extension in websocket.extensions]

    config = Config(
        app=App,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
        ws_per_message_deflate=False,
    )
    async with run_server(config):
        extension_names = await open_connection("ws://127.0.0.1:8000")
        assert "permessage-deflate" not in extension_names


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_close_connection(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.close"})

    async def open_connection(url):
        try:
            await websockets.connect(url)
        except websockets.exceptions.InvalidHandshake:
            return False
        return True  # pragma: no cover

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000")
        assert not is_open


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_headers(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            headers = self.scope.get("headers")
            headers = dict(headers)
            assert headers[b"host"].startswith(b"127.0.0.1")
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000")
        assert is_open


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_extra_headers(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send(
                {"type": "websocket.accept", "headers": [(b"extra", b"header")]}
            )

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.response_headers

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        extra_headers = await open_connection("ws://127.0.0.1:8000")
        assert extra_headers.get("extra") == "header"


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_path_and_raw_path(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            path = self.scope.get("path")
            raw_path = self.scope.get("raw_path")
            assert path == "/one/two"
            assert raw_path == b"/one%2Ftwo"
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000/one%2Ftwo")
        assert is_open


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_text_data_to_client(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "text": "123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        data = await get_data("ws://127.0.0.1:8000")
        assert data == "123"


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_binary_data_to_client(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "bytes": b"123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        data = await get_data("ws://127.0.0.1:8000")
        assert data == b"123"


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_and_close_connection(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "text": "123"})
            await self.send({"type": "websocket.close"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            data = await websocket.recv()
            is_open = True
            try:
                await websocket.recv()
            except Exception:
                is_open = False
            return (data, is_open)

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        (data, is_open) = await get_data("ws://127.0.0.1:8000")
        assert data == "123"
        assert not is_open


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_text_data_to_server(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

        async def websocket_receive(self, message):
            _text = message.get("text")
            await self.send({"type": "websocket.send", "text": _text})

    async def send_text(url):
        async with websockets.connect(url) as websocket:
            await websocket.send("abc")
            return await websocket.recv()

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        data = await send_text("ws://127.0.0.1:8000")
        assert data == "abc"


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_binary_data_to_server(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

        async def websocket_receive(self, message):
            _bytes = message.get("bytes")
            await self.send({"type": "websocket.send", "bytes": _bytes})

    async def send_text(url):
        async with websockets.connect(url) as websocket:
            await websocket.send(b"abc")
            return await websocket.recv()

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        data = await send_text("ws://127.0.0.1:8000")
        assert data == b"abc"


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_after_protocol_close(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "text": "123"})
            await self.send({"type": "websocket.close"})
            with pytest.raises(Exception):
                await self.send({"type": "websocket.send", "text": "123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            data = await websocket.recv()
            is_open = True
            try:
                await websocket.recv()
            except Exception:
                is_open = False
            return (data, is_open)

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        (data, is_open) = await get_data("ws://127.0.0.1:8000")
        assert data == "123"
        assert not is_open


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_missing_handshake(ws_protocol_cls, http_protocol_cls):
    async def app(app, receive, send):
        pass

    async def connect(url):
        await websockets.connect(url)

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.InvalidStatusCode) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.status_code == 500


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_before_handshake(ws_protocol_cls, http_protocol_cls):
    async def app(scope, receive, send):
        await send({"type": "websocket.send", "text": "123"})

    async def connect(url):
        await websockets.connect(url)

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.InvalidStatusCode) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.status_code == 500


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_duplicate_handshake(ws_protocol_cls, http_protocol_cls):
    async def app(scope, receive, send):
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.accept"})

    async def connect(url):
        async with websockets.connect(url) as websocket:
            _ = await websocket.recv()

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.code == 1006


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_asgi_return_value(ws_protocol_cls, http_protocol_cls):
    """
    The ASGI callable should return 'None'. If it doesn't make sure that
    the connection is closed with an error condition.
    """

    async def app(scope, receive, send):
        await send({"type": "websocket.accept"})
        return 123

    async def connect(url):
        async with websockets.connect(url) as websocket:
            _ = await websocket.recv()

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.code == 1006


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
@pytest.mark.parametrize("code", [None, 1000, 1001])
@pytest.mark.parametrize(
    "reason",
    [None, "test", False],
    ids=["none_as_reason", "normal_reason", "without_reason"],
)
async def test_app_close(ws_protocol_cls, http_protocol_cls, code, reason):
    async def app(scope, receive, send):
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.receive":
                reply = {"type": "websocket.close"}

                if code is not None:
                    reply["code"] = code

                if reason is not False:
                    reply["reason"] = reason

                await send(reply)
            elif message["type"] == "websocket.disconnect":
                break

    async def websocket_session(url):
        async with websockets.connect(url) as websocket:
            await websocket.ping()
            await websocket.send("abc")
            await websocket.recv()

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await websocket_session("ws://127.0.0.1:8000")
        assert exc_info.value.code == (code or 1000)
        assert exc_info.value.reason == (reason or "")


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_client_close(ws_protocol_cls, http_protocol_cls):
    async def app(scope, receive, send):
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.receive":
                pass
            elif message["type"] == "websocket.disconnect":
                break

    async def websocket_session(url):
        async with websockets.connect(url) as websocket:
            await websocket.ping()
            await websocket.send("abc")

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        await websocket_session("ws://127.0.0.1:8000")


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_client_connection_lost(ws_protocol_cls, http_protocol_cls):
    got_disconnect_event = False

    async def app(scope, receive, send):
        nonlocal got_disconnect_event
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.disconnect":
                break

        got_disconnect_event = True

    config = Config(
        app=app,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
        ws_ping_interval=0.0,
    )
    async with run_server(config):
        async with websockets.client.connect("ws://127.0.0.1:8000") as websocket:
            websocket.transport.close()
            await asyncio.sleep(0.1)
            got_disconnect_event_before_shutdown = got_disconnect_event

    assert got_disconnect_event_before_shutdown is True


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_connection_lost_before_handshake_complete(
    ws_protocol_cls, http_protocol_cls
):
    send_accept_task = asyncio.Event()
    disconnect_message = {}

    async def app(scope, receive, send):
        nonlocal disconnect_message
        message = await receive()
        if message["type"] == "websocket.connect":
            await send_accept_task.wait()
            await send({"type": "websocket.accept"})
        disconnect_message = await receive()

    async def websocket_session(uri):
        await websockets.client.connect(uri)

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        task = asyncio.create_task(websocket_session("ws://127.0.0.1:8000"))
        await asyncio.sleep(0.1)
        task.cancel()
        send_accept_task.set()

    assert disconnect_message == {"type": "websocket.disconnect", "code": 1006}


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_send_close_on_server_shutdown(ws_protocol_cls, http_protocol_cls):
    disconnect_message = {}

    async def app(scope, receive, send):
        nonlocal disconnect_message
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.disconnect":
                disconnect_message = message
                break

    async def websocket_session(uri):
        async with websockets.client.connect(uri):
            while True:
                await asyncio.sleep(0.1)

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        task = asyncio.create_task(websocket_session("ws://127.0.0.1:8000"))
        await asyncio.sleep(0.1)
        disconnect_message_before_shutdown = disconnect_message

    assert disconnect_message_before_shutdown == {}
    assert disconnect_message == {"type": "websocket.disconnect", "code": 1012}
    task.cancel()


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
@pytest.mark.parametrize("subprotocol", ["proto1", "proto2"])
async def test_subprotocols(ws_protocol_cls, http_protocol_cls, subprotocol):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept", "subprotocol": subprotocol})

    async def get_subprotocol(url):
        async with websockets.connect(
            url, subprotocols=["proto1", "proto2"]
        ) as websocket:
            return websocket.subprotocol

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        accepted_subprotocol = await get_subprotocol("ws://127.0.0.1:8000")
        assert accepted_subprotocol == subprotocol


MAX_WS_BYTES = 1024 * 1024 * 16
MAX_WS_BYTES_PLUS1 = MAX_WS_BYTES + 1


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", ONLY_WEBSOCKETPROTOCOL)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
@pytest.mark.parametrize(
    "client_size_sent, server_size_max, expected_result",
    [
        (MAX_WS_BYTES, MAX_WS_BYTES, 0),
        (MAX_WS_BYTES_PLUS1, MAX_WS_BYTES, 1009),
        (10, 10, 0),
        (11, 10, 1009),
    ],
    ids=[
        "max=defaults sent=defaults",
        "max=defaults sent=defaults+1",
        "max=10 sent=10",
        "max=10 sent=11",
    ],
)
async def test_send_binary_data_to_server_bigger_than_default(
    ws_protocol_cls,
    http_protocol_cls,
    client_size_sent,
    server_size_max,
    expected_result,
):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

        async def websocket_receive(self, message):
            _bytes = message.get("bytes")
            await self.send({"type": "websocket.send", "bytes": _bytes})

    async def send_text(url):
        async with websockets.connect(url, max_size=client_size_sent) as websocket:
            await websocket.send(b"\x01" * client_size_sent)
            return await websocket.recv()

    config = Config(
        app=App,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
        ws_max_size=server_size_max,
    )
    async with run_server(config):
        if expected_result == 0:
            data = await send_text("ws://127.0.0.1:8000")
            assert data == b"\x01" * client_size_sent
        else:
            with pytest.raises(websockets.ConnectionClosedError) as e:
                data = await send_text("ws://127.0.0.1:8000")
            assert e.value.code == expected_result


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_server_reject_connection(ws_protocol_cls, http_protocol_cls):
    async def app(scope, receive, send):
        assert scope["type"] == "websocket"

        # Pull up first recv message.
        message = await receive()
        assert message["type"] == "websocket.connect"

        # Reject the connection.
        await send({"type": "websocket.close"})
        # -- At this point websockets' recv() is unusable. --

        # This doesn't raise `TypeError`:
        # See https://github.com/encode/uvicorn/issues/244
        message = await receive()
        assert message["type"] == "websocket.disconnect"

    async def websocket_session(url):
        try:
            async with websockets.connect(url):
                pass  # pragma: no cover
        except Exception:
            pass

    config = Config(app=app, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        await websocket_session("ws://127.0.0.1:8000")


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_server_can_read_messages_in_buffer_after_close(
    ws_protocol_cls, http_protocol_cls
):
    frames = []
    disconnect_message = {}

    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            # Ensure server doesn't start reading frames from read buffer until
            # after client has sent close frame, but server is still able to
            # read these frames
            await asyncio.sleep(0.2)

        async def websocket_disconnect(self, message):
            nonlocal disconnect_message
            disconnect_message = message

        async def websocket_receive(self, message):
            frames.append(message.get("bytes"))

    async def send_text(url):
        async with websockets.connect(url) as websocket:
            await websocket.send(b"abc")
            await websocket.send(b"abc")
            await websocket.send(b"abc")

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        await send_text("ws://127.0.0.1:8000")

    assert frames == [b"abc", b"abc", b"abc"]
    assert disconnect_message == {"type": "websocket.disconnect", "code": 1000}


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_default_server_headers(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.response_headers

    config = Config(app=App, ws=ws_protocol_cls, http=http_protocol_cls, lifespan="off")
    async with run_server(config):
        headers = await open_connection("ws://127.0.0.1:8000")
        assert headers.get("server") == "uvicorn" and "date" in headers


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_no_server_headers(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.response_headers

    config = Config(
        app=App,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
        server_header=False,
    )
    async with run_server(config):
        headers = await open_connection("ws://127.0.0.1:8000")
        assert "server" not in headers


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", ONLY_WS_PROTOCOL)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_no_date_header(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.response_headers

    config = Config(
        app=App,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
        date_header=False,
    )
    async with run_server(config):
        headers = await open_connection("ws://127.0.0.1:8000")
        assert "date" not in headers


@pytest.mark.anyio
@pytest.mark.parametrize("ws_protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("http_protocol_cls", HTTP_PROTOCOLS)
async def test_multiple_server_header(ws_protocol_cls, http_protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send(
                {
                    "type": "websocket.accept",
                    "headers": [
                        (b"Server", b"over-ridden"),
                        (b"Server", b"another-value"),
                    ],
                }
            )

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.response_headers

    config = Config(
        app=App,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
    )
    async with run_server(config):
        headers = await open_connection("ws://127.0.0.1:8000")
        assert headers.get_all("Server") == ["uvicorn", "over-ridden", "another-value"]
