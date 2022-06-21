import io
import sys
from typing import TYPE_CHECKING, AsyncGenerator, List

import httpx
import pytest

from uvicorn._types import Environ, StartResponse
from uvicorn.middleware.wsgi import WSGIMiddleware, build_environ

if TYPE_CHECKING:
    from asgiref.typing import HTTPRequestEvent, HTTPScope


def hello_world(environ: Environ, start_response: StartResponse) -> List[bytes]:
    status = "200 OK"
    output = b"Hello World!\n"
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(output))),
    ]
    start_response(status, headers, None)
    return [output]


def echo_body(environ: Environ, start_response: StartResponse) -> List[bytes]:
    status = "200 OK"
    output = environ["wsgi.input"].read()
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Content-Length", str(len(output))),
    ]
    start_response(status, headers, None)
    return [output]


def raise_exception(environ: Environ, start_response: StartResponse) -> RuntimeError:
    raise RuntimeError("Something went wrong")


def return_exc_info(environ: Environ, start_response: StartResponse) -> List[bytes]:
    try:
        raise RuntimeError("Something went wrong")
    except RuntimeError:
        status = "500 Internal Server Error"
        output = b"Internal Server Error"
        headers = [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(output))),
        ]
        start_response(status, headers, sys.exc_info())  # type: ignore[arg-type]
        return [output]


@pytest.mark.anyio
async def test_wsgi_get() -> None:
    app = WSGIMiddleware(hello_world)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.text == "Hello World!\n"


@pytest.mark.anyio
async def test_wsgi_post() -> None:
    app = WSGIMiddleware(echo_body)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post("/", json={"example": 123})
    assert response.status_code == 200
    assert response.text == '{"example": 123}'


@pytest.mark.anyio
async def test_wsgi_put_more_body() -> None:
    async def generate_body() -> AsyncGenerator[bytes, None]:
        for _ in range(1024):
            yield b"123456789abcdef\n" * 64

    app = WSGIMiddleware(echo_body)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.put("/", content=generate_body())
    assert response.status_code == 200
    assert response.text == "123456789abcdef\n" * 64 * 1024


@pytest.mark.anyio
async def test_wsgi_exception() -> None:
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(raise_exception)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        with pytest.raises(RuntimeError):
            await client.get("/")


@pytest.mark.anyio
async def test_wsgi_exc_info() -> None:
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(return_exc_info)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        with pytest.raises(RuntimeError):
            response = await client.get("/")

    app = WSGIMiddleware(return_exc_info)
    transport = httpx.ASGITransport(
        app=app,
        raise_app_exceptions=False,
    )
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        response = await client.get("/")
    assert response.status_code == 500
    assert response.text == "Internal Server Error"


def test_build_environ_encoding() -> None:
    scope: "HTTPScope" = {
        "asgi": {"version": "3.0", "spec_version": "2.0"},
        "scheme": "http",
        "raw_path": b"/\xe6\x96\x87",
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/文",
        "root_path": "/文",
        "client": None,
        "server": None,
        "query_string": b"a=123&b=456",
        "headers": [(b"key", b"value1"), (b"key", b"value2")],
        "extensions": {},
    }
    message: "HTTPRequestEvent" = {
        "type": "http.request",
        "body": b"",
        "more_body": False,
    }
    environ = build_environ(scope, message, io.BytesIO(b""))
    assert environ["PATH_INFO"] == "/文".encode("utf8").decode("latin-1")
    assert environ["HTTP_KEY"] == "value1,value2"
