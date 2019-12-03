import asyncio
import threading
import time
import typing

import requests
from requests.adapters import HTTPAdapter

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


def test_run_signal():
    class App:
        def __init__(self, scope):
            if scope["type"] != "http":
                raise Exception()

        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    config = Config(app=App, loop="asyncio", limit_max_requests=1, exit_signals=None)
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


def test_run_signal_multi_threads():
    class App:
        def __init__(self, scope):
            if scope["type"] != "http":
                raise Exception()

        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    def join_t(*threads: threading.Thread) -> typing.List[None]:
        return [t.join() for t in threads]

    def start_threads(*threads: threading.Thread) -> typing.List[None]:
        return [t.start() for t in threads]

    def event_thread(
        worker: typing.Awaitable, loop, *args, **kwargs
    ) -> threading.Thread:
        def _worker(*args, **kwargs):
            try:
                loop.run_until_complete(worker(*args, **kwargs))
            except Exception as e:
                print(e)
            finally:
                loop.close()

        return threading.Thread(target=_worker, args=args, kwargs=kwargs)

    threads_count = 10
    loops = [asyncio.new_event_loop() for i in range(threads_count)]
    for loop in loops:
        asyncio.set_event_loop(loop)
    configs = [
        Config(
            app=App,
            port=10000 + i,
            loop=loops[i],
            limit_max_requests=1,
            exit_signals=None,
        )
        for i in range(threads_count)
    ]
    servers = [Server(config=configs[i]) for i in range(threads_count)]
    workers = [
        event_thread(servers[i].serve, loop=loops[i]) for i in range(threads_count)
    ]
    start_threads(*workers)
    time.sleep(1)
    for x in range(threads_count):
        port = 10000 + x
        s = requests.Session()
        s.mount(f"http://127.0.0.1:{port}", HTTPAdapter(max_retries=1))
        response = s.get(f"http://127.0.0.1:{port}")
        assert response.status_code == 204
    join_t(*workers)
