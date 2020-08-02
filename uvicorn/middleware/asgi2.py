from typing import Callable

from uvicorn._types import ASGIApp_v2


class ASGI2Middleware:
    def __init__(self, app: ASGIApp_v2) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        instance = self.app(scope)
        await instance(receive, send)
