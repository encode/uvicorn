import contextlib
import sys
import threading
import time
import warnings
from functools import partialmethod

import pytest
import requests
from urllib3.exceptions import InsecureRequestWarning

from uvicorn.config import Config
from uvicorn.main import Server


@contextlib.contextmanager
def no_ssl_verification(session=requests.Session):
    old_request = session.request
    session.request = partialmethod(old_request, verify=False)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        yield

    session.request = old_request


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
def test_run(tls_ca_certificate_pem_path, tls_ca_certificate_private_key_path):
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

    config = Config(
        app=App,
        loop="asyncio",
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_path,
        ssl_certfile=tls_ca_certificate_pem_path,
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    with no_ssl_verification():
        response = requests.get("https://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
def test_run_chain(tls_certificate_pem_path):
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

    config = Config(
        app=App,
        loop="asyncio",
        limit_max_requests=1,
        ssl_certfile=tls_certificate_pem_path,
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    with no_ssl_verification():
        response = requests.get("https://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()
