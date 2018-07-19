from uvicorn.protocols.http.h11 import H11Protocol
from uvicorn.protocols.http.httptools import HttpToolsProtocol
import asyncio
import functools
import threading
import requests
import pytest
import websockets
from contextlib import contextmanager


class WebSocketResponse:

    persist = False

    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        self.send = send

        if self.persist:
            while True:
                message = await receive()
                await self.handle(message)
        else:
            message = await receive()
            await self.handle(message)

    async def handle(self, message):
        message_type = message["type"].replace(".", "_")
        handler = getattr(self, message_type)
        await handler(message)


def run_loop(loop):
    loop.run_forever()
    loop.close()


@contextmanager
def run_server(app, protocol_cls):
    asyncio.set_event_loop(None)
    loop = asyncio.new_event_loop()
    protocol = functools.partial(protocol_cls, app=app, loop=loop)
    create_server_task = loop.create_server(protocol, host="127.0.0.1")
    server = loop.run_until_complete(create_server_task)
    url = "ws://127.0.0.1:%d/" % server.sockets[0].getsockname()[1]
    try:
        # Run the event loop in a new thread.
        thread = threading.Thread(target=run_loop, args=[loop])
        thread.start()
        # Return the contextmanager state.
        yield url
    finally:
        # Close the loop from our main thread.
        loop.call_soon_threadsafe(loop.stop)
        thread.join()


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_invalid_upgrade(protocol_cls):

    app = lambda scope: None

    with run_server(app, protocol_cls=protocol_cls) as url:
        url = url.replace("ws://", "http://")
        response = requests.get(
            url, headers={"upgrade": "websocket", "connection": "upgrade"}, timeout=5
        )
        assert response.status_code == 403


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_send_and_close_connection(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.close", "text": "123"})

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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_send_text_data_to_server(protocol_cls):
    class App(WebSocketResponse):

        persist = True

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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_send_binary_data_to_server(protocol_cls):
    class App(WebSocketResponse):

        persist = True

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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
def test_send_after_protocol_close(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.close", "text": "123"})
            with pytest.raises(Exception):
                await self.send({"type": "websocket.send", "text": "1234"})

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


@pytest.mark.parametrize("protocol_cls", [HttpToolsProtocol, H11Protocol])
@pytest.mark.parametrize("acceptable_subprotocol", ["proto1", "proto2"])
def test_subprotocols(protocol_cls, acceptable_subprotocol):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            if acceptable_subprotocol in self.scope["subprotocols"]:
                await self.send(
                    {"type": "websocket.accept", "subprotocol": acceptable_subprotocol}
                )
            else:
                await self.send({"type": "websocket.close"})

    async def get_subprotocol(url):
        async with websockets.connect(
            url, subprotocols=["proto1", "proto2"]
        ) as websocket:
            return websocket.subprotocol

    with run_server(App, protocol_cls=protocol_cls) as url:
        loop = asyncio.new_event_loop()
        subprotocol = loop.run_until_complete(get_subprotocol(url))
        assert subprotocol == acceptable_subprotocol
        loop.close()
