import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from uvicorn import Config, Server


@asynccontextmanager
async def run_server(config: Config, sockets=None):
    server = Server(config=config, sockets=sockets)
    await server.start_serving()
    try:
        yield server
    finally:
        await server.shutdown()


@contextmanager
def as_cwd(path: Path):
    """Changes working directory and returns to previous on exit."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)
