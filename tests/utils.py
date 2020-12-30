import asyncio

try:
    from contextlib import asynccontextmanager
except ImportError:  # pragma: no cover
    from async_generator import asynccontextmanager

from uvicorn import Config, Server


@asynccontextmanager
async def run_server(config: Config, sockets=None):
    signal_event = asyncio.Event()
    shutdown_trigger = signal_event.wait
    server = Server(config=config)
    server.shutdown_trigger = shutdown_trigger
    cancel_handle = asyncio.ensure_future(server.serve(sockets=sockets))
    await asyncio.sleep(0.1)
    try:
        yield server
    finally:
        signal_event.set()
        await server.shutdown()
        cancel_handle.cancel()
