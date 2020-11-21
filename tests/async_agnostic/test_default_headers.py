from typing import Callable

import pytest
import requests

from uvicorn import Config
from uvicorn._async_agnostic import Server


async def app(scope: dict, receive: Callable, send: Callable) -> None:
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_default_headers(async_library: str) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
    )

    with Server(config=config).run_in_thread():
        response = requests.get("http://localhost:8000")
        assert response.headers["server"] == "uvicorn" and response.headers["date"]


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_override_server_header(async_library: str) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
        headers=[("Server", "overridden")],
    )

    with Server(config=config).run_in_thread():
        response = requests.get("http://localhost:8000")
        assert response.headers["server"] == "overridden" and response.headers["date"]


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_override_server_header_multiple_times(async_library: str) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
        headers=[("Server", "overridden"), ("Server", "another-value")],
    )

    with Server(config=config).run_in_thread():
        response = requests.get("http://localhost:8000")
        assert (
            response.headers["server"] == "overridden, another-value"
            and response.headers["date"]
        )


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_add_additional_header(async_library: str) -> None:
    config = Config(
        app=app,
        async_library=async_library,
        limit_max_requests=1,
        headers=[("X-Additional", "new-value")],
    )

    with Server(config=config).run_in_thread():
        response = requests.get("http://localhost:8000")
        assert (
            response.headers["x-additional"] == "new-value"
            and response.headers["server"] == "uvicorn"
            and response.headers["date"]
        )
