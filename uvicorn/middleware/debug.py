import html
import traceback
from typing import Union

from asgiref.typing import (
    ASGI3Application,
    ASGIReceiveCallable,
    ASGISendCallable,
    ASGISendEvent,
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


class DebugMiddleware:
    def __init__(self, app: ASGI3Application):
        self.app = app

    async def __call__(
        self, scope: WWWScope, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        response_started = False

        async def inner_send(message: ASGISendEvent) -> None:
            nonlocal response_started, send

            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, inner_send)
        except BaseException as exc:
            if response_started:
                raise exc from None

            accept = get_accept_header(scope)
            response: Union[HTMLResponse, PlainTextResponse]
            if "text/html" in accept:
                exc_html = html.escape(traceback.format_exc())
                content = (
                    "<html><body><h1>500 Server Error</h1><pre>%s</pre></body></html>"
                    % exc_html
                )
                response = HTMLResponse(content, status_code=500)
            else:
                content = traceback.format_exc()
                response = PlainTextResponse(content, status_code=500)

            await response(scope, receive, send)
            raise exc from None
