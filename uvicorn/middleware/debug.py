from asgiref.typing import (
    ASGIReceiveCallable,
    ASGISendCallable,
    HTTPResponseBodyEvent,
    HTTPResponseStartEvent,
    WWWScope,
)


class HTMLResponse:
    def __init__(self, content: str, status_code: int):
        self.content = content
        self.status_code = status_code

    async def __call__(
        self, scope: WWWScope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        response_start: HTTPResponseStartEvent = {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": [(b"content-type", b"text/html; charset=utf-8")],
        }
        await send(response_start)

        response_body: HTTPResponseBodyEvent = {
            "type": "http.response.body",
            "body": self.content.encode("utf-8"),
            "more_body": False,
        }
        await send(response_body)


class PlainTextResponse:
    def __init__(self, content: str, status_code: int):
        self.content = content
        self.status_code = status_code

    async def __call__(
        self, scope: WWWScope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        response_start: HTTPResponseStartEvent = {
            "type": "http.response.start",
            "status": self.status_code,
            "headers": [(b"content-type", b"text/plain; charset=utf-8")],
        }
        await send(response_start)

        response_body: HTTPResponseBodyEvent = {
            "type": "http.response.body",
            "body": self.content.encode("utf-8"),
            "more_body": False,
        }
        await send(response_body)


def get_accept_header(scope: WWWScope) -> str:
    accept = "*/*"

    for key, value in scope.get("headers", []):
        if key == b"accept":
            accept = value.decode("ascii")
            break

    return accept
