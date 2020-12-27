import httpx
import pytest

from tests.conftest import run_server
from uvicorn import Config

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


async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 204, "headers": []})
    await send({"type": "http.response.body", "body": b"", "more_body": False})


@pytest.mark.asyncio
async def test_trace_logging(capsys):
    config = Config(
        app=app,
        loop="asyncio",
        limit_max_requests=1,
        log_config=test_logging_config,
        log_level="trace",
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    captured = capsys.readouterr()
    assert '"GET / HTTP/1.1" 204' in captured.out
    assert "[TEST_ACCESS] TRACE" not in captured.out


@pytest.mark.asyncio
@pytest.mark.parametrize("http_protocol", [("h11"), ("httptools")])
async def test_access_logging(capsys, http_protocol):
    config = Config(
        app=app,
        loop="asyncio",
        http=http_protocol,
        limit_max_requests=1,
        log_config=test_logging_config,
    )
    async with run_server(config):
        async with httpx.AsyncClient() as client:
            response = await client.get("http://127.0.0.1:8000")

    assert response.status_code == 204
    captured = capsys.readouterr()
    assert '"GET / HTTP/1.1" 204' in captured.out
    assert "uvicorn.access" in captured.out
