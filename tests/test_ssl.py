import contextlib
import sys
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


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
def test_run(tls_ca_certificate_pem_path, tls_ca_certificate_private_key_path, tls_certificate_pem_path):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_path,
        ssl_certfile=tls_ca_certificate_pem_path,
    )
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("https://127.0.0.1:8000", verify=False)
    assert response.status_code == 204
    thread.join()


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
def test_run_chain(tls_certificate_pem_path):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        ssl_certfile=tls_certificate_pem_path,
    )
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("https://127.0.0.1:8000", verify=False)
    assert response.status_code == 204
    thread.join()


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
def test_run_password(
    tls_ca_certificate_pem_path, tls_ca_certificate_private_key_encrypted_path
):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_encrypted_path,
        ssl_certfile=tls_ca_certificate_pem_path,
        ssl_keyfile_password="uvicorn password for the win",
    )
    server = Server(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("https://127.0.0.1:8000", verify=False)
    assert response.status_code == 204
    thread.join()
