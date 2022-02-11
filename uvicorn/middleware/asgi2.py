from asgiref.typing import ASGI2Application, ASGIReceiveCallable, ASGISendCallable


class ASGI2Middleware:
    def __init__(self, app: ASGI2Application):
        self.app = app

    async def __call__(
        self, scope: dict, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        instance = self.app(scope)
        await instance(receive, send)
