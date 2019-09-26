import logging

import pytest

from tests.client import TestClient
from uvicorn.middleware.message_logger import MessageLoggerMiddleware


def test_message_logger(caplog):
    async def app(scope, receive, send):
        message = await receive()
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"", "more_body": False})

    caplog.set_level(logging.DEBUG, logger="uvicorn_access")
    caplog.set_level(logging.DEBUG, logger="uvicorn_error")
    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(["ASGI [1] Started" in message for message in messages]) == 1
    assert sum(["ASGI [1] Sent" in message for message in messages]) == 1
    assert sum(["ASGI [1] Received" in message for message in messages]) == 2
    assert sum(["ASGI [1] Completed" in message for message in messages]) == 1
    assert sum(["ASGI [1] Raised exception" in message for message in messages]) == 0

    sent_to_loggers = [record.name for record in caplog.records]
    assert sum(["uvicorn_access" in name for name in sent_to_loggers]) == 5
    assert sum(["uvicorn_error" in name for name in sent_to_loggers]) == 0

def test_message_logger_exc(caplog):
    async def app(scope, receive, send):
        raise RuntimeError()

    caplog.set_level(logging.DEBUG, logger="uvicorn_access")
    caplog.set_level(logging.DEBUG, logger="uvicorn_error")
    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/")
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(["ASGI [1] Started" in message for message in messages]) == 1
    assert sum(["ASGI [1] Sent" in message for message in messages]) == 0
    assert sum(["ASGI [1] Received" in message for message in messages]) == 0
    assert sum(["ASGI [1] Completed" in message for message in messages]) == 0
    assert sum(["ASGI [1] Raised exception" in message for message in messages]) == 1

    sent_to_loggers = [record.name for record in caplog.records]
    assert sum(["uvicorn_access" in name for name in sent_to_loggers]) == 1
    assert sum(["uvicorn_error" in name for name in sent_to_loggers]) == 1
