from typing import List, Union

import httpx
import pytest
from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, Scope

from tests.response import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


async def app(
    scope: Scope,
    receive: ASGIReceiveCallable,
    send: ASGISendCallable,
) -> None:
    scheme = scope["scheme"]  # type: ignore
    host, port = scope["client"]  # type: ignore
    addr = "%s://%s:%d" % (scheme, host, port)
    response = Response("Remote: " + addr, media_type="text/plain")
    await response(scope, receive, send)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("trusted_hosts", "response_text"),
    [
        # always trust
        ("*", "Remote: https://1.2.3.4:0"),
        # trusted proxy
        ("127.0.0.1", "Remote: https://1.2.3.4:0"),
        (["127.0.0.1"], "Remote: https://1.2.3.4:0"),
        # trusted proxy list
        (["127.0.0.1", "10.0.0.1"], "Remote: https://1.2.3.4:0"),
        ("127.0.0.1, 10.0.0.1", "Remote: https://1.2.3.4:0"),
        # request from untrusted proxy
        ("192.168.0.1", "Remote: http://127.0.0.1:123"),
    ],
)
async def test_proxy_headers_trusted_hosts(
    trusted_hosts: Union[List[str], str], response_text: str
) -> None:
    app_with_middleware = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    async with httpx.AsyncClient(
        app=app_with_middleware, base_url="http://testserver"
    ) as client:
        headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
        response = await client.get("/", headers=headers)

    assert response.status_code == 200
    assert response.text == response_text


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("trusted_hosts", "response_text"),
    [
        # always trust
        ("*", "Remote: https://1.2.3.4:0"),
        # all proxies are trusted
        (
            ["127.0.0.1", "10.0.2.1", "192.168.0.2"],
            "Remote: https://1.2.3.4:0",
        ),
        # order doesn't matter
        (
            ["10.0.2.1", "192.168.0.2", "127.0.0.1"],
            "Remote: https://1.2.3.4:0",
        ),
        # should set first untrusted as remote address
        (["192.168.0.2", "127.0.0.1"], "Remote: https://10.0.2.1:0"),
    ],
)
async def test_proxy_headers_multiple_proxies(
    trusted_hosts: Union[List[str], str], response_text: str
) -> None:
    app_with_middleware = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    async with httpx.AsyncClient(
        app=app_with_middleware, base_url="http://testserver"
    ) as client:
        headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "1.2.3.4, 10.0.2.1, 192.168.0.2",
        }
        response = await client.get("/", headers=headers)

    assert response.status_code == 200
    assert response.text == response_text


@pytest.mark.anyio
async def test_proxy_headers_invalid_x_forwarded_for() -> None:
    app_with_middleware = ProxyHeadersMiddleware(app, trusted_hosts="*")
    async with httpx.AsyncClient(
        app=app_with_middleware, base_url="http://testserver"
    ) as client:
        headers = httpx.Headers(
            {
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "1.2.3.4, \xf0\xfd\xfd\xfd",
            },
            encoding="latin-1",
        )
        response = await client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"
