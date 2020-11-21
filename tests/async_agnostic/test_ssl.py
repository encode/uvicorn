import contextlib
import sys
import warnings
from functools import partialmethod
from typing import Callable

import pytest
import requests
from urllib3.exceptions import InsecureRequestWarning

from uvicorn._async_agnostic import Server
from uvicorn.config import Config


@contextlib.contextmanager
def no_ssl_verification(session=requests.Session):  # type: ignore
    old_request = session.request
    session.request = partialmethod(old_request, verify=False)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", InsecureRequestWarning)
        yield

    session.request = old_request


async def app(scope: dict, receive: Callable, send: Callable) -> None:
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run(
    async_library: str,
    tls_ca_certificate_pem_path: str,
    tls_ca_certificate_private_key_path: str,
) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_path,
        ssl_certfile=tls_ca_certificate_pem_path,
    )

    with Server(config).run_in_thread():
        with no_ssl_verification():
            response = requests.get("https://127.0.0.1:8000")
            assert response.status_code == 204


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run_chain(async_library: str, tls_certificate_pem_path: str) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
        ssl_certfile=tls_certificate_pem_path,
    )

    with Server(config).run_in_thread():
        with no_ssl_verification():
            response = requests.get("https://127.0.0.1:8000")
            assert response.status_code == 204


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping SSL test on Windows"
)
@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run_password(
    async_library: str,
    tls_ca_certificate_pem_path: str,
    tls_ca_certificate_private_key_encrypted_path: str,
) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
        ssl_keyfile=tls_ca_certificate_private_key_encrypted_path,
        ssl_certfile=tls_ca_certificate_pem_path,
        ssl_keyfile_password="uvicorn password for the win",
    )
    with Server(config).run_in_thread():
        with no_ssl_verification():
            response = requests.get("https://127.0.0.1:8000")
            assert response.status_code == 204
