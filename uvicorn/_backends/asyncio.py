import asyncio
import socket
import ssl
from typing import Any, Awaitable, Callable, List, Tuple

from .base import AsyncBackend, AsyncServer, AsyncSocket


class AsyncioSocket(AsyncSocket):
    def __init__(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._reader = reader
        self._writer = writer

    def streams(self) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        return self._reader, self._writer


class AsyncioServer(AsyncServer):
    def __init__(self, server: asyncio.AbstractServer) -> None:
        self._server = server

    @property
    def sockets(self) -> List[socket.SocketType]:
        assert self._server.sockets is not None
        return self._server.sockets

    async def aclose(self) -> None:
        self._server.close()
        await self._server.wait_closed()


class AsyncioBackend(AsyncBackend):
    def run(self, async_fn: Callable, *args: Any, **kwargs: Any) -> None:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(async_fn(*args, **kwargs))

    async def start_server(
        self,
        handler: Callable[[AsyncSocket], Awaitable[None]],
        sock: socket.SocketType = None,
        host: str = None,
        port: int = None,
        uds: str = None,
        ssl_context: ssl.SSLContext = None,
        backlog: int = 2048,
    ) -> AsyncServer:
        async def asyncio_handler(
            reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            _sock = AsyncioSocket(reader, writer)
            await handler(_sock)

        if uds is None:
            server = await asyncio.start_server(
                asyncio_handler,
                sock=sock,
                host=host,
                port=port,
                ssl=ssl_context,
                backlog=backlog,
            )
        else:
            assert sock is None
            assert host is None
            assert port is None
            server = await asyncio.start_unix_server(
                asyncio_handler,
                path=uds,
                ssl=ssl_context,
                backlog=backlog,
            )

        return AsyncioServer(server)
