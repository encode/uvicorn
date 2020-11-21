from typing import Callable

import pytest

from uvicorn._async_agnostic.backends.auto import AutoBackend
from uvicorn._async_agnostic.exceptions import LifespanFailure
from uvicorn._async_agnostic.lifespan import Lifespan
from uvicorn.config import Config


@pytest.mark.anyio
async def test_lifespan_on() -> None:
    startup_complete = False
    shutdown_complete = False

    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        nonlocal startup_complete, shutdown_complete
        message = await receive()
        assert message["type"] == "lifespan.startup"
        startup_complete = True
        await send({"type": "lifespan.startup.complete"})
        message = await receive()
        assert message["type"] == "lifespan.shutdown"
        shutdown_complete = True
        await send({"type": "lifespan.shutdown.complete"})

    config = Config(app=app, lifespan="on")
    lifespan = Lifespan(config)

    async with AutoBackend().start_soon(lifespan.main):
        assert not startup_complete
        assert not shutdown_complete
        await lifespan.startup()
        assert startup_complete
        assert not shutdown_complete
        await lifespan.shutdown()
        assert startup_complete
        assert shutdown_complete


@pytest.mark.anyio
async def test_lifespan_off() -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        pass  # pragma: no cover

    config = Config(app=app, lifespan="off")
    lifespan = Lifespan(config)

    async with AutoBackend().start_soon(lifespan.main):
        await lifespan.startup()
        await lifespan.shutdown()


@pytest.mark.anyio
async def test_lifespan_auto() -> None:
    startup_complete = False
    shutdown_complete = False

    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        nonlocal startup_complete, shutdown_complete
        message = await receive()
        assert message["type"] == "lifespan.startup"
        startup_complete = True
        await send({"type": "lifespan.startup.complete"})
        message = await receive()
        assert message["type"] == "lifespan.shutdown"
        shutdown_complete = True
        await send({"type": "lifespan.shutdown.complete"})

    config = Config(app=app, lifespan="auto")
    lifespan = Lifespan(config)

    async with AutoBackend().start_soon(lifespan.main):
        assert not startup_complete
        assert not shutdown_complete
        await lifespan.startup()
        assert startup_complete
        assert not shutdown_complete
        await lifespan.shutdown()
        assert startup_complete
        assert shutdown_complete


@pytest.mark.anyio
async def test_lifespan_auto_with_error() -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        assert scope["type"] == "http"

    config = Config(app=app, lifespan="auto")
    lifespan = Lifespan(config)

    async with AutoBackend().start_soon(lifespan.main):
        await lifespan.startup()
        await lifespan.shutdown()


@pytest.mark.anyio
async def test_lifespan_on_with_error() -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        assert scope["type"] == "lifespan"
        raise RuntimeError("Oops")

    config = Config(app=app, lifespan="on")
    lifespan = Lifespan(config)

    with pytest.raises(RuntimeError, match="Oops"):
        async with AutoBackend().start_soon(lifespan.main):
            await lifespan.startup()


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ("auto", "on"))
@pytest.mark.parametrize("raise_exception", (True, False))
async def test_lifespan_with_failed_startup(mode: str, raise_exception: bool) -> None:
    async def app(scope: dict, receive: Callable, send: Callable) -> None:
        message = await receive()
        assert message["type"] == "lifespan.startup"
        await send({"type": "lifespan.startup.failed"})
        if raise_exception:
            # App should be able to re-raise an exception if startup failed.
            raise RuntimeError()

    config = Config(app=app, lifespan=mode)
    lifespan = Lifespan(config)

    with pytest.raises(LifespanFailure):
        async with AutoBackend().start_soon(lifespan.main):
            await lifespan.startup()


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ("auto", "on"))
async def test_lifespan_scope_asgi3app(mode: str) -> None:
    async def asgi3app(scope: dict, receive: Callable, send: Callable) -> None:
        assert scope == {
            "type": "lifespan",
            "asgi": {"version": "3.0", "spec_version": "2.0"},
        }

    config = Config(app=asgi3app, lifespan=mode)
    lifespan = Lifespan(config)

    async with AutoBackend().start_soon(lifespan.main):
        await lifespan.startup()
        await lifespan.shutdown()


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ("auto", "on"))
async def test_lifespan_scope_asgi2app(mode: str) -> None:
    def asgi2app(scope: dict) -> Callable:
        assert scope == {
            "type": "lifespan",
            "asgi": {"version": "2.0", "spec_version": "2.0"},
        }

        async def asgi(receive: Callable, send: Callable) -> None:
            pass

        return asgi

    config = Config(app=asgi2app, lifespan=mode)
    lifespan = Lifespan(config)

    async with AutoBackend().start_soon(lifespan.main):
        await lifespan.startup()
        await lifespan.shutdown()
