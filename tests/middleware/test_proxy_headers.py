from tests.client import TestClient
from tests.response import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


def app(scope):
    scheme = scope["scheme"]
    host, port = scope["client"]
    addr = "%s://%s:%d" % (scheme, host, port)
    return Response("Remote: " + addr, media_type="text/plain")


app = ProxyHeadersMiddleware(app)


def test_proxy_headers():
    client = TestClient(app)
    headers = {
        "X-Forwarded-Proto": "https",
        "X-Forwarded-For": "1.2.3.4",
        "X-Forwarded-Port": "567"
    }
    response = client.get('/', headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:567"


def test_proxy_headers_no_port():
    client = TestClient(app)
    headers = {
        "X-Forwarded-Proto": "https",
        "X-Forwarded-For": "1.2.3.4",
    }
    response = client.get('/', headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"
