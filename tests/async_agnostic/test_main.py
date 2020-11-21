from typing import Callable

import pytest
import requests

from uvicorn._async_agnostic import Server
from uvicorn.config import Config


async def app(scope: dict, receive: Callable, send: Callable) -> None:
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
@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run(host: str, url: str, async_library: str) -> None:
    config = Config(
        app=app,
        host=host,
        async_library=async_library,
        limit_max_requests=1,
    )

    with Server(config).run_in_thread():
        response = requests.get(url)
        assert response.status_code == 204


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run_multiprocess(async_library: str) -> None:
    config = Config(
        app=app,
        workers=2,
        async_library=async_library,
        limit_max_requests=1,
    )

    with Server(config).run_in_thread():
        response = requests.get("http://127.0.0.1:8000")
        assert response.status_code == 204


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run_reload(async_library: str) -> None:
    config = Config(
        app=app,
        reload=True,
        async_library=async_library,
        limit_max_requests=1,
    )

    with Server(config).run_in_thread():
        response = requests.get("http://127.0.0.1:8000")
        assert response.status_code == 204


@pytest.mark.parametrize("async_library", ["asyncio", "trio"])
def test_run_with_shutdown(async_library: str) -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        pass

    async def shutdown_immediately() -> None:
        pass

    config = Config(
        app=app,
        workers=2,
        shutdown_trigger=shutdown_immediately,
        async_library=async_library,
    )

    with Server(config).run_in_thread():
        pass
