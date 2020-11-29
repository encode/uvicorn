import socket
import ssl
from typing import Any, Awaitable, Callable, List


class AsyncSocket:
    """
    Base interface for sockets.
    """


class AsyncServer:
    """
    Base interface for running servers.
    """

    @property
    def sockets(self) -> List[socket.SocketType]:
        raise NotImplementedError  # pragma: no cover

    async def aclose(self) -> None:
        raise NotImplementedError  # pragma: no cover


class AsyncBackend:
    """
    Base interface for async operations.

    Abstracts away asyncio-specific APIs.
    """

    def run(self, async_fn: Callable, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError  # pragma: no cover

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
        raise NotImplementedError  # pragma: no cover
