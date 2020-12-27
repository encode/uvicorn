import sys

import httpx
import pytest

from uvicorn.middleware.wsgi import WSGIMiddleware


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


@pytest.mark.asyncio
async def test_wsgi_get():
    app = WSGIMiddleware(hello_world)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.get("/")
    assert response.status_code == 200
    assert response.text == "Hello World!\n"


@pytest.mark.asyncio
async def test_wsgi_post():
    app = WSGIMiddleware(echo_body)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        response = await client.post("/", json={"example": 123})
    assert response.status_code == 200
    assert response.text == '{"example": 123}'


@pytest.mark.asyncio
async def test_wsgi_exception():
    # Note that we're testing the WSGI app directly here.
    # The HTTP protocol implementations would catch this error and return 500.
    app = WSGIMiddleware(raise_exception)
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        with pytest.raises(RuntimeError):
            await client.get("/")


@pytest.mark.asyncio
async def test_wsgi_exc_info():
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
