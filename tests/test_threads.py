import asyncio
import functools
import threading

import pytest
import requests
import websockets

from tests.protocols.test_websocket import WebSocketResponse
from uvicorn import Config
from uvicorn.main import ServerState
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


class UvicornInnaThread(threading.Thread):
    def __init__(self, *args, loop=None, app=None, protocol_cls=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.loop = loop or asyncio.new_event_loop()
        self.running = False
        self.config = Config(app=app, ws=protocol_cls)
        self.server_state = ServerState()
        self.protocol = functools.partial(H11Protocol, config=self.config, server_state=self.server_state)
        self.server_task = self.loop.create_server(self.protocol, host="127.0.0.1")

    @property
    def url(self):
        url = "ws://127.0.0.1:{port}{path}".format(port=self.port, path="/")
        return url

    def run(self):
        self.running = True
        self.loop.run_forever()

    def run_server(self):
        result = asyncio.run_coroutine_threadsafe(self.server_task, loop=self.loop).result()
        self.port = result.sockets[0].getsockname()[1]
        return result

    def run_coro(self, coro):
        result = asyncio.run_coroutine_threadsafe(coro, loop=self.loop).result()
        return result

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.join()
        self.running = False


WS_PROTOCOLS = [p for p in [WSProtocol, WebSocketProtocol] if p is not None]


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_invalid_upgrade(protocol_cls):
    def app(scope):
        pass

    thr = UvicornInnaThread(app=app, protocol_cls=protocol_cls)
    thr.start()
    try:
        thr.run_server()
        url = thr.url.replace("ws://", "http://")
        response = requests.get(
            url, headers={"upgrade": "websocket", "connection": "upgrade"}, timeout=5
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
    except Exception as e:
        raise e
    finally:
        thr.stop()

@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_accept_connection(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            assert False

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    thr = UvicornInnaThread(app=App, protocol_cls=protocol_cls)
    thr.start()
    try:
        thr.run_server()
        thr.run_coro(open_connection(thr.url))
    except Exception as e:
        raise e
    finally:
        thr.stop()
