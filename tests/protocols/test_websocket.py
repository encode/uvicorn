import httpx
import pytest

from tests.utils import run_server
from uvicorn.config import Config
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

try:
    import websockets
    from websockets.extensions.permessage_deflate import ClientPerMessageDeflateFactory

    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
except ImportError:  # pragma: nocover
    websockets = None
    WebSocketProtocol = None
    ClientPerMessageDeflateFactory = None


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


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_invalid_upgrade(protocol_cls):
    def app(scope):
        return None

    config = Config(app=app, ws=protocol_cls)
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "http://127.0.0.1:8000",
                headers={"upgrade": "websocket", "connection": "upgrade"},
                timeout=5,
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


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_accept_connection(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000")
        assert is_open


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_supports_permessage_deflate_extension(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        extension_factories = [ClientPerMessageDeflateFactory()]
        async with websockets.connect(url, extensions=extension_factories) as websocket:
            return [extension.name for extension in websocket.extensions]

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        extension_names = await open_connection("ws://127.0.0.1:8000")
        assert "permessage-deflate" in extension_names


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_close_connection(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.close"})

    async def open_connection(url):
        try:
            await websockets.connect(url)
        except websockets.exceptions.InvalidHandshake:
            return False
        return True  # pragma: no cover

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000")
        assert not is_open


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_headers(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            headers = self.scope.get("headers")
            headers = dict(headers)
            assert headers[b"host"].startswith(b"127.0.0.1")
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000")
        assert is_open


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_path_and_raw_path(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            path = self.scope.get("path")
            raw_path = self.scope.get("raw_path")
            assert path == "/one/two"
            assert raw_path == "/one%2Ftwo"
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        is_open = await open_connection("ws://127.0.0.1:8000/one%2Ftwo")
        assert is_open


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_text_data_to_client(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "text": "123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        data = await get_data("ws://127.0.0.1:8000")
        assert data == "123"


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_binary_data_to_client(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "bytes": b"123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        data = await get_data("ws://127.0.0.1:8000")
        assert data == b"123"


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_and_close_connection(protocol_cls):
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

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        (data, is_open) = await get_data("ws://127.0.0.1:8000")
        assert data == "123"
        assert not is_open


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_text_data_to_server(protocol_cls):
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

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        data = await send_text("ws://127.0.0.1:8000")
        assert data == "abc"


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_binary_data_to_server(protocol_cls):
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

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        data = await send_text("ws://127.0.0.1:8000")
        assert data == b"abc"


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_after_protocol_close(protocol_cls):
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

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        (data, is_open) = await get_data("ws://127.0.0.1:8000")
        assert data == "123"
        assert not is_open


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_missing_handshake(protocol_cls):
    async def app(app, receive, send):
        pass

    async def connect(url):
        await websockets.connect(url)

    config = Config(app=app, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.InvalidStatusCode) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_send_before_handshake(protocol_cls):
    async def app(scope, receive, send):
        await send({"type": "websocket.send", "text": "123"})

    async def connect(url):
        await websockets.connect(url)

    config = Config(app=app, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.InvalidStatusCode) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.status_code == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_duplicate_handshake(protocol_cls):
    async def app(scope, receive, send):
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.accept"})

    async def connect(url):
        async with websockets.connect(url) as websocket:
            _ = await websocket.recv()

    config = Config(app=app, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.code == 1006


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_asgi_return_value(protocol_cls):
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

    config = Config(app=app, ws=protocol_cls, lifespan="off", log_level="trace")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await connect("ws://127.0.0.1:8000")
        assert exc_info.value.code == 1006


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("code", [None, 1000, 1001])
@pytest.mark.parametrize("reason", [None, "test"])
async def test_app_close(protocol_cls, code, reason):
    async def app(scope, receive, send):
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.receive":
                reply = {"type": "websocket.close"}

                if code is not None:
                    reply["code"] = code

                if reason is not None:
                    reply["reason"] = reason

                await send(reply)
            elif message["type"] == "websocket.disconnect":
                break

    async def websocket_session(url):
        async with websockets.connect(url) as websocket:
            await websocket.ping()
            await websocket.send("abc")
            await websocket.recv()

    config = Config(app=app, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc_info:
            await websocket_session("ws://127.0.0.1:8000")
        assert exc_info.value.code == (code or 1000)
        assert exc_info.value.reason == (reason or "")


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
async def test_client_close(protocol_cls):
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

    config = Config(app=app, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        await websocket_session("ws://127.0.0.1:8000")


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("subprotocol", ["proto1", "proto2"])
async def test_subprotocols(protocol_cls, subprotocol):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept", "subprotocol": subprotocol})

    async def get_subprotocol(url):
        async with websockets.connect(
            url, subprotocols=["proto1", "proto2"]
        ) as websocket:
            return websocket.subprotocol

    config = Config(app=App, ws=protocol_cls, lifespan="off")
    async with run_server(config):
        accepted_subprotocol = await get_subprotocol("ws://127.0.0.1:8000")
        assert accepted_subprotocol == subprotocol
