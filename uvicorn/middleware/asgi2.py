from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from uvicorn._types import ASGI2App


class ASGI2Middleware:
    def __init__(self, app: "ASGI2App") -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        instance = self.app(scope)
        await instance(receive, send)
