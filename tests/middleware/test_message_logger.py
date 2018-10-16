from tests.client import TestClient
from uvicorn.middleware.message_logger import MessageLoggerMiddleware
import pytest
import logging


def test_message_logger(caplog):
    def app(scope):
        async def asgi(receive, send):
            message = await receive()
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

        return asgi

    caplog.set_level(logging.DEBUG)
    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(['ASGI [1] Initialized' in message for message in messages]) == 1
    assert sum(['ASGI [1] Started task' in message for message in messages]) == 1
    assert sum(['ASGI [1] Sent' in message for message in messages]) == 1
    assert sum(['ASGI [1] Received' in message for message in messages]) == 2
    assert sum(['ASGI [1] Completed' in message for message in messages]) == 1
    assert sum(['ASGI [1] Raised exception' in message for message in messages]) == 0


def test_message_logger_exc(caplog):
    def app(scope):
        async def asgi(receive, send):
            raise RuntimeError()

        return asgi

    caplog.set_level(logging.DEBUG)
    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/")
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(['ASGI [1] Initialized' in message for message in messages]) == 1
    assert sum(['ASGI [1] Started task' in message for message in messages]) == 1
    assert sum(['ASGI [1] Sent' in message for message in messages]) == 0
    assert sum(['ASGI [1] Received' in message for message in messages]) == 0
    assert sum(['ASGI [1] Completed' in message for message in messages]) == 0
    assert sum(['ASGI [1] Raised exception' in message for message in messages]) == 1


def test_message_logger_scope_exc(caplog):
    def app(scope):
        raise RuntimeError()

    caplog.set_level(logging.DEBUG)
    app = MessageLoggerMiddleware(app)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/")
    messages = [record.msg % record.args for record in caplog.records]
    assert sum(['ASGI [1] Initialized' in message for message in messages]) == 1
    assert sum(['ASGI [1] Started task' in message for message in messages]) == 0
    assert sum(['ASGI [1] Sent' in message for message in messages]) == 0
    assert sum(['ASGI [1] Received' in message for message in messages]) == 0
    assert sum(['ASGI [1] Completed' in message for message in messages]) == 0
    assert sum(['ASGI [1] Raised exception' in message for message in messages]) == 1
