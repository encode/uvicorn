from typing import Generator
import asyncio
import os
import signal
import sys

import pytest

from uvicorn.config import Config
from uvicorn.server import Server


class CaughtSignal(Exception):
    pass


@pytest.fixture(params=[signal.SIGINT, signal.SIGTERM])
def exception_signal(request: "type[pytest.FixtureRequest]") -> Generator[signal.Signals, None, None]:  # pragma: py-win32
    """Fixture that replaces SIGINT/SIGTERM handling with a normal exception"""

    def raise_handler(*_: object) -> None:
        raise CaughtSignal

    original_handler = signal.signal(request.param, raise_handler)
    yield request.param
    signal.signal(request.param, original_handler)


@pytest.fixture(params=[signal.SIGINT, signal.SIGTERM])
def async_exception_signal(request: "type[pytest.FixtureRequest]") -> Generator[signal.Signals, None, None]:  # pragma: py-win32
    """Fixture that replaces SIGINT/SIGTERM handling with a normal exception"""

    def raise_handler(*_: object) -> None:
        raise CaughtSignal

    original_handler = signal.signal(request.param, raise_handler)
    yield request.param
    signal.signal(request.param, original_handler)


async def dummy_app(scope, receive, send):  # pragma: py-win32
    pass


@pytest.mark.anyio
@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like signal handling")
async def test_server_interrupt(exception_signal: signal.Signals):  # pragma: py-win32
    """Test interrupting a Server that is run explicitly inside asyncio"""

    async def interrupt_running(srv: Server):
        while not srv.started:
            await asyncio.sleep(0.01)
        os.kill(os.getpid(), exception_signal)

    server = Server(Config(app=dummy_app, loop="asyncio"))
    asyncio.create_task(interrupt_running(server))
    with pytest.raises(CaughtSignal):
        await server.serve()
    # set by the server's graceful exit handler
    assert server.should_exit
