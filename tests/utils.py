import asyncio
import functools
import os
import sys
from contextlib import contextmanager
from pathlib import Path

if sys.version_info >= (3, 7):
    from contextlib import asynccontextmanager
else:
    from contextlib2 import asynccontextmanager

from uvicorn import Config, Server


def _release_waiter(waiter, *args):
    if not waiter.done():
        waiter.set_result(None)


async def _cancel_and_wait(fut):
    """Cancel the *fut* future or task and wait until it completes."""

    waiter = asyncio.get_event_loop().create_future()
    cb = functools.partial(_release_waiter, waiter)
    fut.add_done_callback(cb)

    try:
        fut.cancel()
        # We cannot wait on *fut* directly to make
        # sure _cancel_and_wait itself is reliably cancellable.
        await waiter
    finally:
        fut.remove_done_callback(cb)


@asynccontextmanager
async def run_server(config: Config, sockets=None):
    server = Server(config=config)
    async with server.serve_acmgr():
        task = asyncio.ensure_future(server.main_loop())
        try:
            yield server
        finally:
            await _cancel_and_wait(task)


@contextmanager
def as_cwd(path: Path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
