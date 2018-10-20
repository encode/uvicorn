import asyncio
from uvicorn.lifespan import Lifespan


class LifespanContext:
    def __init__(self, app):
        self.app = app
        self.lifespan = Lifespan(app)

    async def __aenter__(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.lifespan.run())
        await self.lifespan.wait_startup()
        return self.app

    async def __aexit__(self, exc_type, exc, tb):
        await self.lifespan.wait_shutdown()


def test_lifespan_enabled():
    def enabled_app(scope):
        return True

    def disabled_app(scope):
        raise RuntimeError()

    assert Lifespan(enabled_app).is_enabled
    assert not Lifespan(disabled_app).is_enabled


def test_lifespan():
    startup_complete = False
    cleanup_complete = False

    def app(scope):
        async def lifespan(receive, send):
            nonlocal startup_complete, cleanup_complete
            message = await receive()
            assert message['type'] == 'lifespan.startup'
            startup_complete = True
            await send({'type': 'lifespan.startup.complete'})
            message = await receive()
            assert message['type'] == 'lifespan.shutdown'
            cleanup_complete = True
            await send({'type': 'lifespan.shutdown.complete'})
        return lifespan

    async def test(app):
        assert not startup_complete
        assert not cleanup_complete
        async with LifespanContext(app) as app:
            assert startup_complete
            assert not cleanup_complete
        assert startup_complete
        assert cleanup_complete

    loop = asyncio.new_event_loop()
    loop.run_until_complete(test(app))
