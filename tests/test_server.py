from __future__ import annotations

import asyncio
import contextlib
import signal
import sys
from typing import Callable, ContextManager, Generator

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


if sys.platform == "win32":  # pragma: py-not-win32
    signals = [signal.SIGBREAK]
    signal_captures = [capture_signal_sync]
else:  # pragma: py-win32
    signals = [signal.SIGTERM, signal.SIGINT]
    signal_captures = [capture_signal_sync, capture_signal_async]


@pytest.mark.anyio
@pytest.mark.parametrize("exception_signal", signals)
@pytest.mark.parametrize("capture_signal", signal_captures)
async def test_server_interrupt(
    exception_signal: signal.Signals, capture_signal: Callable[[signal.Signals], ContextManager[None]]
):  # pragma: py-win32
    """Test interrupting a Server that is run explicitly inside asyncio"""

    async def interrupt_running(srv: Server):
        while not srv.started:
            await asyncio.sleep(0.01)
        signal.raise_signal(exception_signal)

    server = Server(Config(app=dummy_app, loop="asyncio"))
    asyncio.create_task(interrupt_running(server))
    with capture_signal(exception_signal) as witness:
        await server.serve()
    assert witness
    # set by the server's graceful exit handler
    assert server.should_exit
