import asyncio

from uvicorn.config import Config
from uvicorn.lifespan.auto import LifespanAuto
from uvicorn.lifespan.off import LifespanOff
from uvicorn.lifespan.on import LifespanOn


def test_auto_lifespan():
    def lifespan_unsupported(scope):
        assert scope["type"] == "http"

    def lifespan_supported(scope):
        pass

    config = Config(app=lifespan_unsupported)
    lifespan = LifespanAuto(config)
    assert isinstance(lifespan, LifespanOff)

    config = Config(app=lifespan_supported)
    lifespan = LifespanAuto(config)
    assert isinstance(lifespan, LifespanOn)


def test_lifespan():
    startup_complete = False
    shutdown_complete = False

    def app(scope):
        async def lifespan(receive, send):
            nonlocal startup_complete, shutdown_complete
            message = await receive()
            assert message["type"] == "lifespan.startup"
            startup_complete = True
            await send({"type": "lifespan.startup.complete"})
            message = await receive()
            assert message["type"] == "lifespan.shutdown"
            shutdown_complete = True
            await send({"type": "lifespan.shutdown.complete"})

        return lifespan

    async def test():
        config = Config(app=app, loop=None)
        lifespan = LifespanOn(config)
        loop = asyncio.get_event_loop()
        loop.create_task(lifespan.run())

        assert not startup_complete
        assert not shutdown_complete
        await lifespan.startup()
        assert startup_complete
        assert not shutdown_complete
        await lifespan.shutdown()
        assert startup_complete
        assert shutdown_complete

    loop = asyncio.new_event_loop()
    loop.run_until_complete(test())
