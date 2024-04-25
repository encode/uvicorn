from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
from typing import Generator

import pytest

from uvicorn.config import Config
from uvicorn.server import Server


# asyncio does NOT allow raising in signal handlers, so to detect
# raised signals raised a mutable `witness` receives the signal
@contextlib.contextmanager
def capture_signal_sync(sig: signal.Signals) -> Generator[list[int], None, None]:
    """Replace `sig` handling with a normal exception via `signal"""
    witness: list[int] = []
    original_handler = signal.signal(sig, lambda signum, frame: witness.append(signum))
    yield witness
    signal.signal(sig, original_handler)


@contextlib.contextmanager
def capture_signal_async(sig: signal.Signals) -> Generator[list[int], None, None]:  # pragma: py-win32
    """Replace `sig` handling with a normal exception via `asyncio"""
    witness: list[int] = []
    original_handler = signal.getsignal(sig)
    asyncio.get_running_loop().add_signal_handler(sig, witness.append, sig)
    yield witness
    signal.signal(sig, original_handler)


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
