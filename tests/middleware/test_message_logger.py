import pytest
from _pytest.logging import LogCaptureFixture

from tests.client import TestClient
from uvicorn._types import ASGI3App, Receive, Scope, Send
from uvicorn.middleware.message_logger import MessageLoggerMiddleware

TRACE_LOG_LEVEL = 5


def test_message_logger(caplog: LogCaptureFixture) -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> ASGI3App:
        await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    caplog.set_level(TRACE_LOG_LEVEL, logger="uvicorn.asgi")
    caplog.set_level(TRACE_LOG_LEVEL)

    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(["ASGI [1] Started" in message for message in messages]) == 1
    assert sum(["ASGI [1] Send" in message for message in messages]) == 2
    assert sum(["ASGI [1] Receive" in message for message in messages]) == 1
    assert sum(["ASGI [1] Completed" in message for message in messages]) == 1
    assert sum(["ASGI [1] Raised exception" in message for message in messages]) == 0


def test_message_logger_exc(caplog: LogCaptureFixture) -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> ASGI3App:
        raise RuntimeError()

    caplog.set_level(TRACE_LOG_LEVEL, logger="uvicorn.asgi")
    caplog.set_level(TRACE_LOG_LEVEL)
    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/")
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(["ASGI [1] Started" in message for message in messages]) == 1
    assert sum(["ASGI [1] Send" in message for message in messages]) == 0
    assert sum(["ASGI [1] Receive" in message for message in messages]) == 0
    assert sum(["ASGI [1] Completed" in message for message in messages]) == 0
    assert sum(["ASGI [1] Raised exception" in message for message in messages]) == 1
