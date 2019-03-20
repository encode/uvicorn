from tests.client import TestClient
from tests.response import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


async def app(scope, receive, send):
    scheme = scope["scheme"]
    host, port = scope["client"]
    addr = "%s://%s:%d" % (scheme, host, port)
    response = Response("Remote: " + addr, media_type="text/plain")
    await response(scope, receive, send)


app = ProxyHeadersMiddleware(app)


def test_proxy_headers():
    client = TestClient(app)
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"


def test_proxy_headers_no_port():
    client = TestClient(app)
    headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
    response = client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"
