import asyncio
import threading
import time

import pytest
import requests
import websockets

from uvicorn.config import Config
from uvicorn.main import Server


def test_run():
    class App:
        def __init__(self, scope):
            if scope["type"] != "http":
                raise Exception()

        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    class CustomServer(Server):
        def install_signal_handlers(self):
            pass

    config = Config(app=App, loop="asyncio", limit_max_requests=1)
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


@pytest.mark.parametrize("ws", ("auto", "websockets", "wsproto"))
def test_run_websocket(ws):
    class App:
        def __init__(self, scope):
            assert scope["type"] == "websocket"
            self.scope = scope

        async def __call__(self, receive, send):
            while True:
                message = await receive()
                message_type = message["type"].replace(".", "_")
                handler = getattr(self, message_type, None)
                if handler is not None:
                    await handler(message, send)
                if message_type == "websocket_disconnect":
                    break

        async def websocket_connect(self, message, send):
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.send", "text": "123"})

    class CustomServer(Server):
        def install_signal_handlers(self):
            pass

    config = Config(app=App, loop="asyncio", ws=ws, limit_max_requests=1)
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)

    async def client():
        websocket = await websockets.connect("ws://127.0.0.1:8000")
        message = await websocket.recv()
        server.handle_exit(None, None)
        try:
            await websocket.recv()
        except websockets.exceptions.ConnectionClosed as exc:
            close_exc = exc

        return message, close_exc

    loop = asyncio.get_event_loop()
    message, close_exc = loop.run_until_complete(client())

    assert message == "123"
    assert close_exc.code == 1001
    thread.join()
