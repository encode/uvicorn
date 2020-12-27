import httpx
import pytest

from tests.response import Response
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware


async def app(scope, receive, send):
    scheme = scope["scheme"]
    host, port = scope["client"]
    addr = "%s://%s:%d" % (scheme, host, port)
    response = Response("Remote: " + addr, media_type="text/plain")
    await response(scope, receive, send)


app = ProxyHeadersMiddleware(app, trusted_hosts="*")


@pytest.mark.asyncio
async def test_proxy_headers():
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
        response = await client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"


@pytest.mark.asyncio
async def test_proxy_headers_no_port():
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        headers = {"X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"}
        response = await client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"


@pytest.mark.asyncio
async def test_proxy_headers_invalid_x_forwarded_for():
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as client:
        headers = {
            "X-Forwarded-Proto": "https",
            "X-Forwarded-For": "\xf0\xfd\xfd\xfd, 1.2.3.4",
        }
        response = await client.get("/", headers=headers)
    assert response.status_code == 200
    assert response.text == "Remote: https://1.2.3.4:0"
