from __future__ import annotations

from typing import TYPE_CHECKING

import httpx
import pytest
import websockets.client

from tests.response import Response
from tests.utils import run_server
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.config import Config
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

if TYPE_CHECKING:
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


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
async def test_proxy_headers_trusted_hosts(trusted_hosts: list[str] | str, response_text: str) -> None:
    app_with_middleware = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    transport = httpx.ASGITransport(app=app_with_middleware)  # type: ignore
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
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
async def test_proxy_headers_multiple_proxies(trusted_hosts: list[str] | str, response_text: str) -> None:
    app_with_middleware = ProxyHeadersMiddleware(app, trusted_hosts=trusted_hosts)
    transport = httpx.ASGITransport(app=app_with_middleware)  # type: ignore
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
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
    transport = httpx.ASGITransport(app=app_with_middleware)  # type: ignore
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
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


@pytest.mark.anyio
@pytest.mark.parametrize(
    "x_forwarded_proto,addr",
    [
        ("http", "ws://1.2.3.4:0"),
        ("https", "wss://1.2.3.4:0"),
        ("ws", "ws://1.2.3.4:0"),
        ("wss", "wss://1.2.3.4:0"),
    ],
)
async def test_proxy_headers_websocket_x_forwarded_proto(
    x_forwarded_proto: str,
    addr: str,
    ws_protocol_cls: type[WSProtocol | WebSocketProtocol],
    http_protocol_cls: type[H11Protocol | HttpToolsProtocol],
    unused_tcp_port: int,
) -> None:
    async def websocket_app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
        assert scope["type"] == "websocket"
        scheme = scope["scheme"]
        assert scope["client"] is not None
        host, port = scope["client"]
        addr = "%s://%s:%d" % (scheme, host, port)
        await send({"type": "websocket.accept"})
        await send({"type": "websocket.send", "text": addr})

    app_with_middleware = ProxyHeadersMiddleware(websocket_app, trusted_hosts="*")
    config = Config(
        app=app_with_middleware,
        ws=ws_protocol_cls,
        http=http_protocol_cls,
        lifespan="off",
        port=unused_tcp_port,
    )

    async with run_server(config):
        url = f"ws://127.0.0.1:{unused_tcp_port}"
        headers = {"X-Forwarded-Proto": x_forwarded_proto, "X-Forwarded-For": "1.2.3.4"}
        async with websockets.client.connect(url, extra_headers=headers) as websocket:
            data = await websocket.recv()
            assert data == addr
