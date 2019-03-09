import threading
import time

import requests

from uvicorn import Config, Server


class App:
    def __init__(self, scope):
        if scope["type"] != "http":
            raise Exception()

    async def __call__(self, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})


class CustomServer(Server):
    def install_signal_handlers(self):
        pass


def test_default_default_headers():
    config = Config(app=App, loop="asyncio", limit_max_requests=1)
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get('http://127.0.0.1:8000')

    assert (response.headers['server'] == 'uvicorn'
            and response.headers['date'])

    thread.join()


def test_override_server_header():
    config = Config(
        app=App, loop="asyncio", limit_max_requests=1,
        custom_headers=[('Server', 'over-ridden')])
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get('http://127.0.0.1:8000')

    assert (response.headers['server'] == 'over-ridden' and
            response.headers['date'])

    thread.join()


def test_override_server_header_multiple_times():
    config = Config(
        app=App, loop="asyncio", limit_max_requests=1,
        custom_headers=[
            ('Server', 'over-ridden'),
            ('Server', 'another-value')])
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get('http://127.0.0.1:8000')

    assert (response.headers['server'] == 'over-ridden, another-value' and
            response.headers['date'])

    thread.join()


def test_override_date_header():
    config = Config(
        app=App, loop="asyncio", limit_max_requests=1,
        custom_headers=[('Date', 'over-ridden')])
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get('http://127.0.0.1:8000')

    assert (response.headers['server'] == 'uvicorn' and
            response.headers['date'] == 'over-ridden')

    thread.join()


def test_add_additional_header():
    config = Config(
        app=App, loop="asyncio", limit_max_requests=1,
        custom_headers=[('X-Additional', 'new-value')])
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get('http://127.0.0.1:8000')

    assert (response.headers['x-additional'] == 'new-value' and
            response.headers['server'] == 'uvicorn' and
            response.headers['date'])

    thread.join()
