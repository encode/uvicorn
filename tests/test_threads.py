import asyncio
import functools
import threading
from contextlib import contextmanager

import pytest
import websockets

from tests.protocols.test_websocket import WebSocketResponse
from uvicorn import Config
from uvicorn.main import ServerState
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

# import logging
# logger = logging.getLogger('websockets')
# logger.setLevel(logging.DEBUG)
# logger.addHandler(logging.StreamHandler())
#
# logger1 = logging.getLogger('wsproto')
# logger1.setLevel(logging.DEBUG)
# logger1.addHandler(logging.StreamHandler())


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

    def __enter__(self):
        self._cm_obj = self._cm()
        self._cm_obj.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self._cm_obj.__exit__(exc_type, exc_val, exc_tb)

    @contextmanager
    def _cm(self):
        try:
            self.start()
            self.run_server()
            yield
        except BaseException as exc:
            raise exc  # comment to suppess exception
        finally:
            self.stop()

    def run(self):
        self.running = True
        self.loop.run_forever()

    def run_server(self):
        result = asyncio.run_coroutine_threadsafe(self.server_task, loop=self.loop).result()
        self.port = result.sockets[0].getsockname()[1]
        return result

    def run_coro(self, coro):
        try:
            result = asyncio.run_coroutine_threadsafe(coro, loop=self.loop).result()
        except Exception as e:
            raise e
        return result

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.join()
        self.running = False


WS_PROTOCOLS = [p for p in [WSProtocol, WebSocketProtocol] if p is not None]


@pytest.mark.parametrize("protocol_cls", WS_PROTOCOLS)
def test_accept_connection_should_raise(protocol_cls):
    class App(WebSocketResponse):
        async def websocket_connect(self, message):
            await self.send({"type": "websocket.accept"})
            raise RuntimeWarning

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    with UvicornInnaThread(app=App, protocol_cls=protocol_cls) as thr:
        try:
            thr.run_coro(open_connection(thr.url))
        except Exception as e:
            raise e
        finally:
            print('finally')
