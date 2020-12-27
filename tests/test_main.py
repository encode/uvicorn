import asyncio
import threading
import time

import pytest
import requests

from uvicorn.config import Config
from uvicorn.main import Server


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.parametrize(
    "host, url",
    [
        pytest.param(None, "http://127.0.0.1:8000", id="default"),
        pytest.param("localhost", "http://127.0.0.1:8000", id="hostname"),
        pytest.param("::1", "http://[::1]:8000", id="ipv6"),
    ],
)
def test_run(host, url):
    config = Config(app=app, host=host, loop="asyncio", limit_max_requests=1)
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get(url)
    assert response.status_code == 204
    thread.join()


def test_run_multiprocess():
    config = Config(app=app, loop="asyncio", workers=2, limit_max_requests=1)
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


def test_run_reload():
    config = Config(app=app, loop="asyncio", reload=True, limit_max_requests=1)
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


def test_run_with_shutdown():
    async def app(scope, receive, send):
        assert scope["type"] == "http"
        while True:
            time.sleep(1)

    config = Config(app=app, loop="asyncio", workers=2, limit_max_requests=1)
    server = Server(config=config)
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
