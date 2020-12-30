import threading
import time

import pytest
import requests

from tests.conftest import CustomServer
from uvicorn.config import Config


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
    config = Config(
        app=app, host=host, lifespan="off", loop="asyncio", limit_max_requests=1
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get(url)
    assert response.status_code == 204
    server.signal_event.set()
    thread.join()


def test_run_multiprocess():
    config = Config(
        app=app, loop="asyncio", lifespan="off", workers=2, limit_max_requests=1
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204

    server.signal_event.set()
    thread.join()


def test_run_reload():
    config = Config(
        app=app, loop="asyncio", lifespan="off", reload=True, limit_max_requests=1
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    server.signal_event.set()
    thread.join()
