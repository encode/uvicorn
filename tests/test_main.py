import threading
import time
import asyncio

import requests

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


def test_run_multiprocess():
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

    config = Config(app=App, loop="asyncio", workers=2, limit_max_requests=1)
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


def test_run_reload():
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

    config = Config(app=App, loop="asyncio", reload=True, limit_max_requests=1)
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


def test_run_with_shutdown():
    class App:
        def __init__(self, scope):
            if scope["type"] != "http":
                raise Exception()

        async def __call__(self, receive, send):
            while True:
                time.sleep(1)

    class CustomServer(Server):
        def install_signal_handlers(self):
            pass

    config = Config(app=App, loop="asyncio", workers=2, limit_max_requests=1)
    server = CustomServer(config=config)
    sock = config.bind_socket()
    exc = True

    def safe_run():
        nonlocal exc, server
        try:
            exc = None
            config.setup_event_loop()
            loop = asyncio.get_event_loop()
            loop.run_until_complete(server.serve(sockets=[sock]))
        except Exception as e:
            exc = e

    thread = threading.Thread(target=safe_run)
    thread.start()

    while not server.started:
        time.sleep(0.01)

    server.should_exit = True
    thread.join()
    assert exc is None
