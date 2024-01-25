from typing import TYPE_CHECKING, List, Type, Union

import httpx
import pytest
import websockets.client

from tests.response import Response
from tests.utils import run_server
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.config import Config
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware, _TrustedHosts

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


# Note: we vary the format here to also test some of the functionality
# of the _TrustedHosts.__init__ method.
_TRUSTED_NOTHING: List[str] = []
_TRUSTED_EVERYTHING = "*"
_TRUSTED_IPv4_ADDRESSES = "127.0.0.1, 10.0.0.1"
_TRUSTED_IPv4_NETWORKS = ["127.0.0.0/8", "10.0.0.0/8"]
_TRUSTED_IPv6_ADDRESSES = [
    "2001:db8::",
    "2001:0db8:0001:0000:0000:0ab9:C0A8:0102",
    "2001:db8:3333:4444:5555:6666:1.2.3.4",  # This is a dual address
    "::11.22.33.44",  # This is a dual address
]
_TRUSTED_IPv6_NETWORKS = "2001:db8:abcd:0012::0/64"
_TRUSTED_LITERALS = "some-literal , unix:///foo/bar  ,  /foo/bar"


@pytest.mark.parametrize(
    ("init_hosts", "test_host", "expected"),
    [
        ## Never Trust trust
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_EVERYTHING, "127.0.0.0", False),
        (_TRUSTED_EVERYTHING, "127.0.0.1", False),
        (_TRUSTED_EVERYTHING, "127.1.1.1", False),
        (_TRUSTED_EVERYTHING, "127.255.255.255", False),
        (_TRUSTED_EVERYTHING, "10.0.0.0", False),
        (_TRUSTED_EVERYTHING, "10.0.0.1", False),
        (_TRUSTED_EVERYTHING, "10.1.1.1", False),
        (_TRUSTED_EVERYTHING, "10.255.255.255", False),
        (_TRUSTED_EVERYTHING, "192.168.0.0", False),
        (_TRUSTED_EVERYTHING, "192.168.0.1", False),
        (_TRUSTED_EVERYTHING, "1.1.1.1", False),
        # Test IPv6 Addresses
        (_TRUSTED_EVERYTHING, "2001:db8::", False),
        (_TRUSTED_EVERYTHING, "2001:db8:abcd:0012::0", False),
        (_TRUSTED_EVERYTHING, "2001:db8:abcd:0012::1:1", False),
        (_TRUSTED_EVERYTHING, "::", False),
        (_TRUSTED_EVERYTHING, "::1", False),
        (
            _TRUSTED_EVERYTHING,
            "2001:db8:3333:4444:5555:6666:102:304",
            False,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_EVERYTHING, "::b16:212c", False),  # aka ::11.22.33.44
        (_TRUSTED_EVERYTHING, "a:b:c:d::", False),
        (_TRUSTED_EVERYTHING, "::a:b:c:d", False),
        # Test Literals
        (_TRUSTED_EVERYTHING, "some-literal", False),
        (_TRUSTED_EVERYTHING, "unix::///foo/bar", False),
        (_TRUSTED_EVERYTHING, "/foo/bar", False),
        (_TRUSTED_EVERYTHING, "*", False),
        (_TRUSTED_EVERYTHING, "another-literal", False),
        (_TRUSTED_EVERYTHING, "unix:///another/path", False),
        (_TRUSTED_EVERYTHING, "/another/path", False),
        ## Always trust
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_EVERYTHING, "127.0.0.0", True),
        (_TRUSTED_EVERYTHING, "127.0.0.1", True),
        (_TRUSTED_EVERYTHING, "127.1.1.1", True),
        (_TRUSTED_EVERYTHING, "127.255.255.255", True),
        (_TRUSTED_EVERYTHING, "10.0.0.0", True),
        (_TRUSTED_EVERYTHING, "10.0.0.1", True),
        (_TRUSTED_EVERYTHING, "10.1.1.1", True),
        (_TRUSTED_EVERYTHING, "10.255.255.255", True),
        (_TRUSTED_EVERYTHING, "192.168.0.0", True),
        (_TRUSTED_EVERYTHING, "192.168.0.1", True),
        (_TRUSTED_EVERYTHING, "1.1.1.1", True),
        # Test IPv6 Addresses
        (_TRUSTED_EVERYTHING, "2001:db8::", True),
        (_TRUSTED_EVERYTHING, "2001:db8:abcd:0012::0", True),
        (_TRUSTED_EVERYTHING, "2001:db8:abcd:0012::1:1", True),
        (_TRUSTED_EVERYTHING, "::", True),
        (_TRUSTED_EVERYTHING, "::1", True),
        (
            _TRUSTED_EVERYTHING,
            "2001:db8:3333:4444:5555:6666:102:304",
            True,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_EVERYTHING, "::b16:212c", True),  # aka ::11.22.33.44
        (_TRUSTED_EVERYTHING, "a:b:c:d::", True),
        (_TRUSTED_EVERYTHING, "::a:b:c:d", True),
        # Test Literals
        (_TRUSTED_EVERYTHING, "some-literal", True),
        (_TRUSTED_EVERYTHING, "unix::///foo/bar", True),
        (_TRUSTED_EVERYTHING, "/foo/bar", True),
        (_TRUSTED_EVERYTHING, "*", True),
        (_TRUSTED_EVERYTHING, "another-literal", True),
        (_TRUSTED_EVERYTHING, "unix:///another/path", True),
        (_TRUSTED_EVERYTHING, "/another/path", True),
        ## Trust IPv4 Addresses
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_IPv4_ADDRESSES, "127.0.0.0", False),
        (_TRUSTED_IPv4_ADDRESSES, "127.0.0.1", True),
        (_TRUSTED_IPv4_ADDRESSES, "127.1.1.1", False),
        (_TRUSTED_IPv4_ADDRESSES, "127.255.255.255", False),
        (_TRUSTED_IPv4_ADDRESSES, "10.0.0.0", False),
        (_TRUSTED_IPv4_ADDRESSES, "10.0.0.1", True),
        (_TRUSTED_IPv4_ADDRESSES, "10.1.1.1", False),
        (_TRUSTED_IPv4_ADDRESSES, "10.255.255.255", False),
        (_TRUSTED_IPv4_ADDRESSES, "192.168.0.0", False),
        (_TRUSTED_IPv4_ADDRESSES, "192.168.0.1", False),
        (_TRUSTED_IPv4_ADDRESSES, "1.1.1.1", False),
        # Test IPv6 Addresses
        (_TRUSTED_IPv4_ADDRESSES, "2001:db8::", False),
        (_TRUSTED_IPv4_ADDRESSES, "2001:db8:abcd:0012::0", False),
        (_TRUSTED_IPv4_ADDRESSES, "2001:db8:abcd:0012::1:1", False),
        (_TRUSTED_IPv4_ADDRESSES, "::", False),
        (_TRUSTED_IPv4_ADDRESSES, "::1", False),
        (
            _TRUSTED_IPv4_ADDRESSES,
            "2001:db8:3333:4444:5555:6666:102:304",
            False,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_IPv4_ADDRESSES, "::b16:212c", False),  # aka ::11.22.33.44
        (_TRUSTED_IPv4_ADDRESSES, "a:b:c:d::", False),
        (_TRUSTED_IPv4_ADDRESSES, "::a:b:c:d", False),
        # Test Literals
        (_TRUSTED_IPv4_ADDRESSES, "some-literal", False),
        (_TRUSTED_IPv4_ADDRESSES, "unix::///foo/bar", False),
        (_TRUSTED_IPv4_ADDRESSES, "*", False),
        (_TRUSTED_IPv4_ADDRESSES, "/foo/bar", False),
        (_TRUSTED_IPv4_ADDRESSES, "another-literal", False),
        (_TRUSTED_IPv4_ADDRESSES, "unix:///another/path", False),
        (_TRUSTED_IPv4_ADDRESSES, "/another/path", False),
        ## Trust IPv6 Addresses
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_IPv6_ADDRESSES, "127.0.0.0", False),
        (_TRUSTED_IPv6_ADDRESSES, "127.0.0.1", False),
        (_TRUSTED_IPv6_ADDRESSES, "127.1.1.1", False),
        (_TRUSTED_IPv6_ADDRESSES, "127.255.255.255", False),
        (_TRUSTED_IPv6_ADDRESSES, "10.0.0.0", False),
        (_TRUSTED_IPv6_ADDRESSES, "10.0.0.1", False),
        (_TRUSTED_IPv6_ADDRESSES, "10.1.1.1", False),
        (_TRUSTED_IPv6_ADDRESSES, "10.255.255.255", False),
        (_TRUSTED_IPv6_ADDRESSES, "192.168.0.0", False),
        (_TRUSTED_IPv6_ADDRESSES, "192.168.0.1", False),
        (_TRUSTED_IPv6_ADDRESSES, "1.1.1.1", False),
        # Test IPv6 Addresses
        (_TRUSTED_IPv6_ADDRESSES, "2001:db8::", True),
        (_TRUSTED_IPv6_ADDRESSES, "2001:db8:abcd:0012::0", False),
        (_TRUSTED_IPv6_ADDRESSES, "2001:db8:abcd:0012::1:1", False),
        (_TRUSTED_IPv6_ADDRESSES, "::", False),
        (_TRUSTED_IPv6_ADDRESSES, "::1", False),
        (
            _TRUSTED_IPv6_ADDRESSES,
            "2001:db8:3333:4444:5555:6666:102:304",
            True,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_IPv6_ADDRESSES, "::b16:212c", True),  # aka ::11.22.33.44
        (_TRUSTED_IPv6_ADDRESSES, "a:b:c:d::", False),
        (_TRUSTED_IPv6_ADDRESSES, "::a:b:c:d", False),
        # Test Literals
        (_TRUSTED_IPv6_ADDRESSES, "some-literal", False),
        (_TRUSTED_IPv6_ADDRESSES, "unix::///foo/bar", False),
        (_TRUSTED_IPv6_ADDRESSES, "*", False),
        (_TRUSTED_IPv6_ADDRESSES, "/foo/bar", False),
        (_TRUSTED_IPv6_ADDRESSES, "another-literal", False),
        (_TRUSTED_IPv6_ADDRESSES, "unix:///another/path", False),
        (_TRUSTED_IPv6_ADDRESSES, "/another/path", False),
        ## Trust IPv4 Networks
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_IPv4_NETWORKS, "127.0.0.0", True),
        (_TRUSTED_IPv4_NETWORKS, "127.0.0.1", True),
        (_TRUSTED_IPv4_NETWORKS, "127.1.1.1", True),
        (_TRUSTED_IPv4_NETWORKS, "127.255.255.255", True),
        (_TRUSTED_IPv4_NETWORKS, "10.0.0.0", True),
        (_TRUSTED_IPv4_NETWORKS, "10.0.0.1", True),
        (_TRUSTED_IPv4_NETWORKS, "10.1.1.1", True),
        (_TRUSTED_IPv4_NETWORKS, "10.255.255.255", True),
        (_TRUSTED_IPv4_NETWORKS, "192.168.0.0", False),
        (_TRUSTED_IPv4_NETWORKS, "192.168.0.1", False),
        (_TRUSTED_IPv4_NETWORKS, "1.1.1.1", False),
        # Test IPv6 Addresses
        (_TRUSTED_IPv4_NETWORKS, "2001:db8::", False),
        (_TRUSTED_IPv4_NETWORKS, "2001:db8:abcd:0012::0", False),
        (_TRUSTED_IPv4_NETWORKS, "2001:db8:abcd:0012::1:1", False),
        (_TRUSTED_IPv4_NETWORKS, "::", False),
        (_TRUSTED_IPv4_NETWORKS, "::1", False),
        (
            _TRUSTED_IPv4_NETWORKS,
            "2001:db8:3333:4444:5555:6666:102:304",
            False,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_IPv4_NETWORKS, "::b16:212c", False),  # aka ::11.22.33.44
        (_TRUSTED_IPv4_NETWORKS, "a:b:c:d::", False),
        (_TRUSTED_IPv4_NETWORKS, "::a:b:c:d", False),
        # Test Literals
        (_TRUSTED_IPv4_NETWORKS, "some-literal", False),
        (_TRUSTED_IPv4_NETWORKS, "unix::///foo/bar", False),
        (_TRUSTED_IPv4_NETWORKS, "*", False),
        (_TRUSTED_IPv4_NETWORKS, "/foo/bar", False),
        (_TRUSTED_IPv4_NETWORKS, "another-literal", False),
        (_TRUSTED_IPv4_NETWORKS, "unix:///another/path", False),
        (_TRUSTED_IPv4_NETWORKS, "/another/path", False),
        ## Trust IPv6 Networks
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_IPv6_NETWORKS, "127.0.0.0", False),
        (_TRUSTED_IPv6_NETWORKS, "127.0.0.1", False),
        (_TRUSTED_IPv6_NETWORKS, "127.1.1.1", False),
        (_TRUSTED_IPv6_NETWORKS, "127.255.255.255", False),
        (_TRUSTED_IPv6_NETWORKS, "10.0.0.0", False),
        (_TRUSTED_IPv6_NETWORKS, "10.0.0.1", False),
        (_TRUSTED_IPv6_NETWORKS, "10.1.1.1", False),
        (_TRUSTED_IPv6_NETWORKS, "10.255.255.255", False),
        (_TRUSTED_IPv6_NETWORKS, "192.168.0.0", False),
        (_TRUSTED_IPv6_NETWORKS, "192.168.0.1", False),
        (_TRUSTED_IPv6_NETWORKS, "1.1.1.1", False),
        # Test IPv6 Addresses
        (_TRUSTED_IPv6_NETWORKS, "2001:db8::", False),
        (_TRUSTED_IPv6_NETWORKS, "2001:db8:abcd:0012::0", True),
        (_TRUSTED_IPv6_NETWORKS, "2001:db8:abcd:0012::1:1", True),
        (_TRUSTED_IPv6_NETWORKS, "::", False),
        (_TRUSTED_IPv6_NETWORKS, "::1", False),
        (
            _TRUSTED_IPv6_NETWORKS,
            "2001:db8:3333:4444:5555:6666:102:304",
            False,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_IPv6_NETWORKS, "::b16:212c", False),  # aka ::11.22.33.44
        (_TRUSTED_IPv6_NETWORKS, "a:b:c:d::", False),
        (_TRUSTED_IPv6_NETWORKS, "::a:b:c:d", False),
        # Test Literals
        (_TRUSTED_IPv6_NETWORKS, "some-literal", False),
        (_TRUSTED_IPv6_NETWORKS, "unix::///foo/bar", False),
        (_TRUSTED_IPv6_NETWORKS, "*", False),
        (_TRUSTED_IPv6_NETWORKS, "/foo/bar", False),
        (_TRUSTED_IPv6_NETWORKS, "another-literal", False),
        (_TRUSTED_IPv6_NETWORKS, "unix:///another/path", False),
        (_TRUSTED_IPv6_NETWORKS, "/another/path", False),
        ## Trust Literals
        ## -----------------------------
        # Test IPv4 Addresses
        (_TRUSTED_LITERALS, "127.0.0.0", False),
        (_TRUSTED_LITERALS, "127.0.0.1", False),
        (_TRUSTED_LITERALS, "127.1.1.1", False),
        (_TRUSTED_LITERALS, "127.255.255.255", False),
        (_TRUSTED_LITERALS, "10.0.0.0", False),
        (_TRUSTED_LITERALS, "10.0.0.1", False),
        (_TRUSTED_LITERALS, "10.1.1.1", False),
        (_TRUSTED_LITERALS, "10.255.255.255", False),
        (_TRUSTED_LITERALS, "192.168.0.0", False),
        (_TRUSTED_LITERALS, "192.168.0.1", False),
        (_TRUSTED_LITERALS, "1.1.1.1", False),
        # Test IPv6 Addresses
        (_TRUSTED_LITERALS, "2001:db8::", False),
        (_TRUSTED_LITERALS, "2001:db8:abcd:0012::0", False),
        (_TRUSTED_LITERALS, "2001:db8:abcd:0012::1:1", False),
        (_TRUSTED_LITERALS, "::", False),
        (_TRUSTED_LITERALS, "::1", False),
        (
            _TRUSTED_LITERALS,
            "2001:db8:3333:4444:5555:6666:102:304",
            False,
        ),  # aka 2001:db8:3333:4444:5555:6666:1.2.3.4
        (_TRUSTED_LITERALS, "::b16:212c", False),  # aka ::11.22.33.44
        (_TRUSTED_LITERALS, "a:b:c:d::", False),
        (_TRUSTED_LITERALS, "::a:b:c:d", False),
        # Test Literals
        (_TRUSTED_LITERALS, "some-literal", True),
        (_TRUSTED_LITERALS, "unix::///foo/bar", True),
        (_TRUSTED_LITERALS, "*", False),
        (_TRUSTED_LITERALS, "/foo/bar", True),
        (_TRUSTED_LITERALS, "another-literal", False),
        (_TRUSTED_LITERALS, "unix:///another/path", False),
        (_TRUSTED_LITERALS, "/another/path", False),
    ],
)
def test_forwarded_hosts(
    init_hosts: Union[str, List[str]], test_host: str, expected: bool
) -> None:
    trusted_hosts = _TrustedHosts(init_hosts)
    assert test_host in trusted_hosts is expected


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
        # trusted proxy network
        # https://github.com/encode/uvicorn/issues/1068#issuecomment-1004813267
        ("127.0.0.0/24, 10.0.0.1", "Remote: https://1.2.3.4:0"),
        # request from untrusted proxy
        ("192.168.0.1", "Remote: http://127.0.0.1:123"),
        # request from untrusted proxy network
        ("192.168.0.0/16", "Remote: http://127.0.0.1:123"),
        # request from client running on proxy server itself
        # https://github.com/encode/uvicorn/issues/1068#issuecomment-855371576
        (["127.0.0.1", "1.2.3.4"], "Remote: https://1.2.3.4:0"),
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
        # Mixed literals and networks
        (["127.0.0.1", "10.0.0.0/8", "192.168.0.2"], "Remote: https://1.2.3.4:0"),
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


@pytest.mark.anyio
async def test_proxy_headers_websocket_x_forwarded_proto(
    ws_protocol_cls: "Type[WSProtocol | WebSocketProtocol]",
    http_protocol_cls: "Type[H11Protocol | HttpToolsProtocol]",
    unused_tcp_port: int,
) -> None:
    async def websocket_app(scope, receive, send):
        scheme = scope["scheme"]
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
        headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
        async with websockets.client.connect(url, extra_headers=headers) as websocket:
            data = await websocket.recv()
            assert data == "wss://1.2.3.4:0"


@pytest.mark.anyio
async def test_proxy_headers_empty_x_forwarded_for() -> None:
    # fallback to the default behavior if x-forwarded-for is an empty list
    # https://github.com/encode/uvicorn/issues/1068#issuecomment-855371576
    app_with_middleware = ProxyHeadersMiddleware(app, trusted_hosts="*")
    transport = httpx.ASGITransport(app=app_with_middleware, client=("1.2.3.4", 8080))
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        headers = httpx.Headers(
            {
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "",
            },
            encoding="latin-1",
        )
        response = await client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:8080"
