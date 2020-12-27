import threading
import time

import requests

from uvicorn import Config, Server


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


def test_default_default_headers():
    config = Config(app=app, loop="asyncio", limit_max_requests=1)
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")

    assert response.headers["server"] == "uvicorn" and response.headers["date"]

    thread.join()


def test_override_server_header():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("Server", "over-ridden")],
    )
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")

    assert response.headers["server"] == "over-ridden" and response.headers["date"]

    thread.join()


def test_override_server_header_multiple_times():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("Server", "over-ridden"), ("Server", "another-value")],
    )
    server = Server(config=config)
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


def test_add_additional_header():
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        headers=[("X-Additional", "new-value")],
    )
    server = Server(config=config)
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
