import asyncio
import functools
import threading
import time
from contextlib import contextmanager

import pytest
import requests

from uvicorn.config import Config
from uvicorn.main import ServerState
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

try:
    import websockets
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
except ImportError:  # pragma: nocover
    websockets = None
    WebSocketProtocol = None


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


def run_loop(loop):
    loop.run_forever()
    loop.close()


@contextmanager
def run_server(app, protocol_cls, path="/"):
    asyncio.set_event_loop(None)
    loop = asyncio.new_event_loop()
    config = Config(app=app, ws=protocol_cls)
    server_state = ServerState()
    protocol = functools.partial(H11Protocol, config=config, server_state=server_state)
    create_server_task = loop.create_server(protocol, host="127.0.0.1")
    server = loop.run_until_complete(create_server_task)
    port = server.sockets[0].getsockname()[1]
    url = "ws://127.0.0.1:{port}{path}".format(port=port, path=path)
    try:
        # Run the event loop in a new thread.
        thread = threading.Thread(target=run_loop, args=[loop])
        thread.start()
        # Return the contextmanager state.
        yield url
    finally:
        # Close the loop from our main thread.
        while server_state.tasks:
            time.sleep(0.01)
        loop.call_soon_threadsafe(loop.stop)
        thread.join()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_invalid_upgrade(protocol_cls):

    app = lambda scope: None

    with run_server(app, protocol_cls=protocol_cls) as url:
        url = url.replace("ws://", "http://")
        response = requests.get(
            url, headers={"upgrade": "websocket", "connection": "upgrade"}, timeout=5
        )
        if response.status_code == 426:
            # response.text == ""
            pass  # ok, wsproto 0.13
        else:
            assert response.status_code == 400
            assert response.text in [
                "Missing Sec-WebSocket-Key header\n",
                "Missing Sec-WebSocket-Version header",  # websockets
                "Missing or empty Sec-WebSocket-Key header\n",  # wsproto
            ]


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_accept_connection(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        is_open = loop.run_until_complete(open_connection(url))
        assert is_open
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_close_connection(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.close"})

    async def open_connection(url):
        try:
            await websockets.connect(url)
        except websockets.exceptions.InvalidHandshake:
            return False
        return True  # pragma: no cover

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        is_open = loop.run_until_complete(open_connection(url))
        assert not is_open
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_headers(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            headers = self.scope.get("headers")
            headers = dict(headers)
            assert headers[b"host"].startswith(b"127.0.0.1")
            await self.send({"type": "websocket.accept"})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        is_open = loop.run_until_complete(open_connection(url))
        assert is_open
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_path_and_raw_path(protocol_cls):
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

    with run_server(App, protocol_cls=protocol_cls, path="/one%2Ftwo") as url:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(open_connection(url))
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_text_data_to_client(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "text": "123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(get_data(url))
        assert data == "123"
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_binary_data_to_client(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            await self.send({"type": "websocket.send", "bytes": b"123"})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(get_data(url))
        assert data == b"123"
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_and_close_connection(protocol_cls):
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
            except:
                is_open = False
            return (data, is_open)

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        (data, is_open) = loop.run_until_complete(get_data(url))
        assert data == "123"
        assert not is_open
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_text_data_to_server(protocol_cls):
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

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(send_text(url))
        assert data == "abc"
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_binary_data_to_server(protocol_cls):
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

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(send_text(url))
        assert data == b"abc"
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_after_protocol_close(protocol_cls):
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
            except:
                is_open = False
            return (data, is_open)

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        (data, is_open) = loop.run_until_complete(get_data(url))
        assert data == "123"
        assert not is_open
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_missing_handshake(protocol_cls):
    class App:
        def __init__(self, scope):
            pass

        async def __call__(self, receive, send):
            pass

    async def connect(url):
        await websockets.connect(url)

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        with pytest.raises(websockets.exceptions.InvalidStatusCode) as exc:
            loop.run_until_complete(connect(url))
        assert exc.value.status_code == 500
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_send_before_handshake(protocol_cls):
    class App:
        def __init__(self, scope):
            pass

        async def __call__(self, receive, send):
            await send({"type": "websocket.send", "text": "123"})

    async def connect(url):
        await websockets.connect(url)

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        with pytest.raises(websockets.exceptions.InvalidStatusCode) as exc:
            loop.run_until_complete(connect(url))
        assert exc.value.status_code == 500
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_duplicate_handshake(protocol_cls):
    class App:
        def __init__(self, scope):
            pass

        async def __call__(self, receive, send):
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.accept"})

    async def connect(url):
        async with websockets.connect(url) as websocket:
            data = await websocket.recv()

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc:
            loop.run_until_complete(connect(url))
        assert exc.value.code == 1006
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_asgi_return_value(protocol_cls):
    """
    The ASGI callable should return 'None'. If it doesn't make sure that
    the connection is closed with an error condition.
    """

    async def app(scope, receive, send):
        await send({"type": "websocket.accept"})
        return 123

    async def connect(url):
        async with websockets.connect(url) as websocket:
            data = await websocket.recv()

    with run_server(app, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc:
            loop.run_until_complete(connect(url))
        assert exc.value.code == 1006
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_app_close(protocol_cls):
    async def app(scope, receive, send):
        while True:
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.accept"})
            elif message["type"] == "websocket.receive":
                await send({"type": "websocket.close"})
            elif message["type"] == "websocket.disconnect":
                break

    async def websocket_session(url):
        async with websockets.connect(url) as websocket:
            await websocket.ping()
            await websocket.send("abc")
            await websocket.recv()

    with run_server(app, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        with pytest.raises(websockets.exceptions.ConnectionClosed) as exc:
            loop.run_until_complete(websocket_session(url))
        assert exc.value.code == 1000
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_client_close(protocol_cls):
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

    with run_server(app, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(websocket_session(url))
        loop.close()


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
@pytest.mark.parametrize("subprotocol", ["proto1", "proto2"])
def test_subprotocols(protocol_cls, subprotocol):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept", "subprotocol": subprotocol})

    async def get_subprotocol(url):
        async with websockets.connect(
            url, subprotocols=["proto1", "proto2"]
        ) as websocket:
            return websocket.subprotocol

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        accepted_subprotocol = loop.run_until_complete(get_subprotocol(url))
        assert accepted_subprotocol == subprotocol
        loop.close()
