from uvicorn._types import ASGI2App, Receive, Scope, Send


class ASGI2Middleware:
    def __init__(self, app: ASGI2App) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        instance = self.app(scope)
        await instance(receive, send)
