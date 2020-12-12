import contextlib
import logging
import platform
import sys
import threading
import time

import pytest
import requests

from uvicorn import Config, Server


@contextlib.contextmanager
def caplog_for_logger(caplog, logger_name):
    logger = logging.getLogger(logger_name)
    if logger.propagate:
        logger.propagate = False
    logger.addHandler(caplog.handler)
    try:
        yield caplog
    finally:
        logger.removeHandler(caplog.handler)


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.skipif(
    sys.platform.startswith("win") or platform.python_implementation() == "PyPy",
    reason="Skipping test on Windows and PyPy",
)
def test_trace_logging(caplog):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        log_level="trace",
    )
    with caplog_for_logger(caplog, "uvicorn.asgi"):
        server = Server(config=config)
        thread = threading.Thread(target=server.run)
        thread.start()
        while not server.started:
            time.sleep(0.01)
        response = requests.get("http://127.0.0.1:8000")
        assert response.status_code == 204
        thread.join()
        messages = [
            record.message for record in caplog.records if record.name == "uvicorn.asgi"
        ]
        assert "ASGI [1] Started scope=" in messages.pop(0)
        assert "ASGI [1] Raised exception" in messages.pop(0)
        assert "ASGI [2] Started scope=" in messages.pop(0)
        assert "ASGI [2] Send " in messages.pop(0)
        assert "ASGI [2] Send " in messages.pop(0)
        assert "ASGI [2] Completed" in messages.pop(0)


@pytest.mark.skipif(
    sys.platform.startswith("win") or platform.python_implementation() == "PyPy",
    reason="Skipping test on Windows and PyPy",
)
@pytest.mark.parametrize("http_protocol", [("h11"), ("httptools")])
def test_access_logging(caplog, http_protocol):
    config = Config(
        app=app,
        loop="asyncio",
        http=http_protocol,
        limit_max_requests=1,
    )
    with caplog_for_logger(caplog, "uvicorn.access"):
        server = Server(config=config)
        thread = threading.Thread(target=server.run)
        thread.start()
        while not server.started:
            time.sleep(0.01)
        response = requests.get("http://127.0.0.1:8000")
        assert response.status_code == 204
        thread.join()
        messages = [
            record.message
            for record in caplog.records
            if record.name == "uvicorn.access"
        ]
        assert '"GET / HTTP/1.1" 204' in messages.pop()


@pytest.mark.parametrize("http_protocol", ["h11", "httptools"])
def test_default_logging(caplog, http_protocol):
    config = Config(
        app=app,
        loop="asyncio",
        http=http_protocol,
        limit_max_requests=1,
    )

    with caplog_for_logger(caplog, "uvicorn.access"):
        server = Server(config=config)
        thread = threading.Thread(target=server.run)
        thread.start()
        while not server.started:
            time.sleep(0.01)
        response = requests.get("http://127.0.0.1:8000")
        assert response.status_code == 204
        thread.join()

        messages = [
            record.message for record in caplog.records if "uvicorn" in record.name
        ]
        assert "Started server process" in messages.pop(0)
        assert "Waiting for application startup" in messages.pop(0)
        assert "ASGI 'lifespan' protocol appears unsupported" in messages.pop(0)
        assert "Application startup complete" in messages.pop(0)
        assert "Uvicorn running on http://127.0.0.1:8000" in messages.pop(0)
        assert '"GET / HTTP/1.1" 204' in messages.pop(0)
        assert "Shutting down" in messages.pop(0)
        assert "Finished server process" in messages.pop(0)
