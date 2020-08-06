import asyncio
import io
import typing
from urllib.parse import unquote, urljoin, urlparse

import requests

from uvicorn._types import Message


class _HeaderDict(requests.packages.urllib3._collections.HTTPHeaderDict):
    def get_all(self, key, default):
        return self.getheaders(key)


class _MockOriginalResponse(object):
    """
    We have to jump through some hoops to present the response as if
    it was made using urllib3.
    """

    def __init__(self, headers):
        self.msg = _HeaderDict(headers)
        self.closed = False

    def isclosed(self):
        return self.closed


class _ASGIAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, app: typing.Callable, raise_server_exceptions=True) -> None:
        self.app = app
        self.raise_server_exceptions = raise_server_exceptions

    def send(self, request, *args, **kwargs):
        scheme, netloc, path, params, query, fragement = urlparse(request.url)
        if ":" in netloc:
            host, port = netloc.split(":", 1)
            port = int(port)
        else:
            host = netloc
            port = {"http": 80, "ws": 80, "https": 443, "wss": 443}[scheme]

        # Include the 'host' header.
        if "host" in request.headers:
            headers = []
        elif port == 80:
            headers = [[b"host", host.encode()]]
        else:
            headers = [[b"host", ("%s:%d" % (host, port)).encode()]]

        # Include other request headers.
        headers += [
            [key.lower().encode(), value.encode()]
            for key, value in request.headers.items()
        ]

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "root_path": "",
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": ["testclient", 50000],
            "server": [host, port],
        }

        async def receive():
            body = request.body
            if body is None:
                body_bytes = b""
            else:
                assert isinstance(body, bytes)
                body_bytes = body
            return {"type": "http.request", "body": body_bytes}

        raw_kwargs = {"body": io.BytesIO()}
        response_started = False

        async def send(message: Message):
            nonlocal raw_kwargs, response_started

            if message["type"] == "http.response.start":
                raw_kwargs["version"] = 11
                raw_kwargs["status"] = message["status"]
                raw_kwargs["headers"] = [
                    (key.decode(), value.decode()) for key, value in message["headers"]
                ]
                raw_kwargs["preload_content"] = False
                raw_kwargs["original_response"] = _MockOriginalResponse(
                    raw_kwargs["headers"]
                )
                response_started = True
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                raw_kwargs["body"].write(body)
                if not more_body:
                    raw_kwargs["body"].seek(0)

        loop = asyncio.get_event_loop()

        try:
            loop.run_until_complete(self.app(scope, receive, send))
        except BaseException as exc:
            if self.raise_server_exceptions:
                raise exc from None

        raw = requests.packages.urllib3.HTTPResponse(**raw_kwargs)
        return self.build_response(request, raw)


class _TestClient(requests.Session):
    def __init__(
        self, app: typing.Callable, base_url: str, raise_server_exceptions=True
    ) -> None:
        super(_TestClient, self).__init__()
        adapter = _ASGIAdapter(app, raise_server_exceptions=raise_server_exceptions)
        self.mount("http://", adapter)
        self.mount("https://", adapter)
        self.headers.update({"user-agent": "testclient"})
        self.base_url = base_url

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        url = urljoin(self.base_url, url)
        return super().request(method, url, **kwargs)


def TestClient(
    app: typing.Callable,
    base_url: str = "http://testserver",
    raise_server_exceptions=True,
) -> _TestClient:
    """
    We have to work around py.test discovery attempting to pick up
    the `TestClient` class, by declaring this as a function.
    """
    return _TestClient(app, base_url, raise_server_exceptions=raise_server_exceptions)
