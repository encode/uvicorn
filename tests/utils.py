import asyncio
import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from uvicorn import Config, Server


@asynccontextmanager
async def run_server(config: Config, sockets=None):
    server = Server(config=config)
    cancel_handle = asyncio.ensure_future(server.serve(sockets=sockets))
    await asyncio.sleep(0.1)
    try:
        yield server
    finally:
        await server.shutdown()
        cancel_handle.cancel()


@contextmanager
def as_cwd(path: Path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
