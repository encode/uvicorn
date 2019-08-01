class ASGI2Middleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        instance = self.app(scope)
        await instance(receive, send)
