from typing import Callable


class ASGI2Middleware:
    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        instance = self.app(scope)
        await instance(receive, send)
