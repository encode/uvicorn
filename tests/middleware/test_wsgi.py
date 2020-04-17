import sys
import asyncio
from tempfile import TemporaryFile

import pytest

from tests.client import TestClient
from uvicorn.middleware.wsgi import WSGIMiddleware, Body


def test_body():
    recv_event = asyncio.Event()
    body = Body(recv_event)
    body.write(
        b"""This is a body test.
Why do this?
To prevent memory leaks.
And cancel pre-reading.
Newline.0
Newline.1
Newline.2
Newline.3
"""
    )
    body.feed_eof()
    assert body.readline() == b"This is a body test.\n"
    assert body.readline(6) == b"Why do"
    assert body.readline(20) == b" this?\n"

    assert body.readlines(2) == [
        b"To prevent memory leaks.\n",
        b"And cancel pre-reading.\n",
    ]
    for index, line in enumerate(body):
        assert line == b"Newline." + str(index).encode("utf8") + b"\n"
        if index == 1:
            break
    assert body.readlines() == [
        b"Newline.2\n",
        b"Newline.3\n",
    ]


def hello_world(environ, start_response):
    status = "200 OK"
    output = b"Hello World!\n"
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(output))),
    ]
    start_response(status, headers)
    return [output]


def echo_body(environ, start_response):
    status = "200 OK"
    output = environ["wsgi.input"].read()
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(output))),
    ]
    start_response(status, headers)
    return [output]


def raise_exception(environ, start_response):
    raise RuntimeError("Something went wrong")


def return_exc_info(environ, start_response):
    try:
        raise RuntimeError("Something went wrong")
    except RuntimeError:
        status = "500 Internal Server Error"
        output = b"Internal Server Error"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(output))),
        ]
        start_response(status, headers, exc_info=sys.exc_info())
        return [output]


def test_wsgi_get():
    app = WSGIMiddleware(hello_world)
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "Hello World!\n"


def test_wsgi_post():
    app = WSGIMiddleware(echo_body)
    client = TestClient(app)
    response = client.post("/", json={"example": 123})
    assert response.status_code == 200
    assert response.text == '{"example": 123}'


def test_wsgi_post_big_file():
    app = WSGIMiddleware(echo_body)
    client = TestClient(app)
    file = TemporaryFile()
    for num in range(1000000):
        file.write(str(num).encode("utf8"))
    response = client.post("/", files={"file": file})
    assert response.status_code == 200
    assert response.content


def test_wsgi_exception():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(raise_exception)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        client.get("/")


def test_wsgi_exc_info():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(return_exc_info)
    client = TestClient(app)
    with pytest.raises(RuntimeError):
        response = client.get("/")

    app = WSGIMiddleware(return_exc_info)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"
