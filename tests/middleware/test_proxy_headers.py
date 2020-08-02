from tests.client import TestClient
from tests.response import Response
from uvicorn._types import Receive, Scope, Send
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    scheme = scope["scheme"]
    host, port = scope["client"]
    addr = "%s://%s:%d" % (scheme, host, port)
    response = Response("Remote: " + addr, media_type="text/plain")
    await response(scope, receive, send)


app = ProxyHeadersMiddleware(app, trusted_hosts="*")


def test_proxy_headers() -> None:
    client = TestClient(app)
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"


def test_proxy_headers_no_port() -> None:
    client = TestClient(app)
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"
