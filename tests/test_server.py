from __future__ import annotations

import asyncio
import signal
import sys

import pytest

from uvicorn.config import Config
from uvicorn.server import Server


async def dummy_app(scope, receive, send):  # pragma: py-win32
    pass


signals = [signal.SIGTERM, signal.SIGINT]
if sys.platform == "win32":
    signals += [signal.SIGBREAK]


@pytest.mark.anyio
@pytest.mark.parametrize("exception_signal", signals)
async def test_server_interrupt(exception_signal: signal.Signals):  # pragma: py-win32
    """Test interrupting a Server that is run explicitly inside asyncio"""

    async def interrupt_running(srv: Server):
        while not srv.started:
            await asyncio.sleep(0.01)
        signal.raise_signal(exception_signal)

    server = Server(Config(app=dummy_app, loop="asyncio"))
    original_handler = signal.getsignal(exception_signal)

    asyncio.create_task(interrupt_running(server))
    await server.serve()

    assert signal.getsignal(exception_signal) == original_handler
    # set by the server's graceful exit handler
    assert server.should_exit


@pytest.mark.anyio
async def test_server_interrupt_force_exit_on_double_sigint():  # pragma: py-win32
    """Test interrupting a Server  on double SIGINT that is run explicitly inside asyncio"""

    sigint = signal.SIGINT

    async def interrupt_running(srv: Server):
        while not srv.started:
            await asyncio.sleep(0.01)
        signal.raise_signal(sigint)
        signal.raise_signal(sigint)

    server = Server(Config(app=dummy_app, loop="asyncio"))
    original_handler = signal.getsignal(sigint)

    asyncio.create_task(interrupt_running(server))
    await server.serve()
    assert server.should_exit
    assert server.force_exit

    assert signal.getsignal(sigint) == original_handler
