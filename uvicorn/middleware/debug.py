import html
import traceback
from typing import Union

from uvicorn._types import ASGI3App, Message, Receive, Scope, Send


class HTMLResponse:
    def __init__(self, content: str, status_code: int) -> None:
        self.content = content
        self.status_code = status_code

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [[b"content-type", b"text/html; charset=utf-8"]],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": self.content.encode("utf-8"),
                "more_body": False,
            }
        )


class PlainTextResponse:
    def __init__(self, content: str, status_code: int) -> None:
        self.content = content
        self.status_code = status_code

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": self.status_code,
                "headers": [[b"content-type", b"text/plain; charset=utf-8"]],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": self.content.encode("utf-8"),
                "more_body": False,
            }
        )


def get_accept_header(scope: Scope) -> str:
    accept = "*/*"

    for key, value in scope.get("headers", []):
        if key == b"accept":
            accept = value.decode("ascii")
            break

    return accept


class DebugMiddleware:
    def __init__(self, app: ASGI3App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        response_started = False

        async def inner_send(message: Message) -> None:
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
            response: Union[PlainTextResponse, HTMLResponse]
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
