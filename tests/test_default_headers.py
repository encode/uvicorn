import threading
import time

import pytest
import requests

from uvicorn import Config, Server

HTTP11_IMPLEMENTATIONS = ["h11"]

try:
    import httptools  # noqa: F401
except ImportError:
    pass
else:
    HTTP11_IMPLEMENTATIONS.append("httptools")


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


class CustomServer(Server):
    def install_signal_handlers(self):
        pass


@pytest.mark.parametrize("async_library", [None, "asyncio"])
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
def test_default_default_headers(async_library, http):
    config = Config(
        app=app,
        loop="asyncio",
        async_library=async_library,
        http=http,
        limit_max_requests=1,
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")

    assert response.headers["server"] == "uvicorn" and response.headers["date"]

    thread.join()


@pytest.mark.parametrize("async_library", [None, "asyncio"])
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
def test_override_server_header(async_library, http):
    config = Config(
        app=app,
        loop="asyncio",
        async_library=async_library,
        http=http,
        limit_max_requests=1,
        headers=[("Server", "over-ridden")],
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")

    assert response.headers["server"] == "over-ridden" and response.headers["date"]

    thread.join()


@pytest.mark.parametrize("async_library", [None, "asyncio"])
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
def test_override_server_header_multiple_times(async_library, http):
    config = Config(
        app=app,
        loop="asyncio",
        async_library=async_library,
        http=http,
        limit_max_requests=1,
        headers=[("Server", "over-ridden"), ("Server", "another-value")],
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")

    assert (
        response.headers["server"] == "over-ridden, another-value"
        and response.headers["date"]
    )

    thread.join()


@pytest.mark.parametrize("async_library", [None, "asyncio"])
@pytest.mark.parametrize("http", HTTP11_IMPLEMENTATIONS)
def test_add_additional_header(async_library, http):
    config = Config(
        app=app,
        loop="asyncio",
        async_library=async_library,
        http=http,
        limit_max_requests=1,
        headers=[("X-Additional", "new-value")],
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")

    assert (
        response.headers["x-additional"] == "new-value"
        and response.headers["server"] == "uvicorn"
        and response.headers["date"]
    )

    thread.join()
