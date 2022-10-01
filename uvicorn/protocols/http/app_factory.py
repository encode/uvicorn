from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asgiref.typing import (
        ASGI3Application as ASGIApp,
        ASGIReceiveCallable,
        ASGISendCallable,
        HTTPResponseBodyEvent,
        HTTPResponseStartEvent,
        Scope,
    )


def create_app(status_code: int, message: str) -> "ASGIApp":
    """
    Create an ASGI application that always returns the given status code and message
    in the body.

    Used for handling errors in the HTTP protocol implementations.
    """

    async def app(
        scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
    ) -> None:
        response_start: "HTTPResponseStartEvent" = {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"content-length", str(len(message)).encode("ascii")),
                (b"connection", b"close"),
            ],
        }
        await send(response_start)

        response_body: "HTTPResponseBodyEvent" = {
            "type": "http.response.body",
            "body": message.encode("utf-8"),
            "more_body": False,
        }
        await send(response_body)

    return app
