import platform
import sys
import threading
import time

import pytest
import requests

from uvicorn import Config, Server

test_logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "test_formatter_default": {
            "format": "[TEST_DEFAULT] %(levelname)-9s %(name)s - %(lineno)d - %(message)s"  # noqa: E501
        },
        "test_formatter_access": {
            "format": "[TEST_ACCESS] %(levelname)-9s %(name)s - %(lineno)d - %(message)s"  # noqa: E501
        },
        "test_formatter_asgi": {
            "format": "[TEST_ASGI] %(levelname)-9s %(name)s - %(lineno)d - %(message)s"
        },
    },
    "handlers": {
        "default": {
            "formatter": "test_formatter_default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
        },
        "access": {
            "formatter": "test_formatter_access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "asgi": {
            "formatter": "test_formatter_asgi",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        "uvicorn.asgi": {"handlers": ["asgi"], "level": "TRACE", "propagate": False},
    },
}


@pytest.mark.skipif(
    sys.platform.startswith("win") or platform.python_implementation() == "PyPy",
    reason="Skipping test on Windows and PyPy",
)
def test_trace_logging(capsys):
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
        log_config=test_logging_config,
        log_level="trace",
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()
    captured = capsys.readouterr()
    assert '"GET / HTTP/1.1" 204' in captured.out
    assert "[TEST_ACCESS] TRACE" not in captured.out


@pytest.mark.skipif(
    sys.platform.startswith("win") or platform.python_implementation() == "PyPy",
    reason="Skipping test on Windows and PyPy",
)
@pytest.mark.parametrize("http_protocol", [("h11"), ("httptools")])
def test_access_logging(capsys, http_protocol):
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
        http=http_protocol,
        limit_max_requests=1,
        log_config=test_logging_config,
    )
    server = CustomServer(config=config)
    thread = threading.Thread(target=server.run)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()
    captured = capsys.readouterr()
    assert '"GET / HTTP/1.1" 204' in captured.out
    assert "uvicorn.access" in captured.out
