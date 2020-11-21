import functools
import signal
import socket
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncIterator,
    Awaitable,
    Callable,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
)

import trio

from ...config import Config
from ..exceptions import BrokenSocket
from ..state import ServerState
from ..utils import get_sock_local_addr, get_sock_remote_addr
from .base import (
    AsyncBackend,
    AsyncListener,
    AsyncSocket,
    Event,
    Queue,
    TaskHandle,
    TaskStatus,
)


class TrioEvent(Event):
    def __init__(self) -> None:
        self._event = trio.Event()

    async def set(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def clear(self) -> None:
        self._event = trio.Event()


class TrioSocket(AsyncSocket):
    def __init__(self, stream: Union[trio.SocketStream, trio.SSLStream]) -> None:
        self._stream = stream
        self._is_closed = False

    def _unwrap_ssl(self) -> trio.SocketStream:
        stream: trio.abc.Stream = self._stream
        while isinstance(stream, trio.SSLStream):
            stream = stream.transport_stream
        assert isinstance(stream, trio.SocketStream)
        return stream

    def get_local_addr(self) -> Optional[Tuple[str, int]]:
        stream = self._unwrap_ssl()
        return get_sock_local_addr(stream.socket)

    def get_remote_addr(self) -> Optional[Tuple[str, int]]:
        stream = self._unwrap_ssl()
        return get_sock_remote_addr(stream.socket)

    @property
    def is_ssl(self) -> bool:
        return isinstance(self._stream, trio.SSLStream)

    async def read(self, n: int) -> bytes:
        try:
            return await self._stream.receive_some(n)
        except (trio.BrokenResourceError, trio.ClosedResourceError):
            return b""

    async def write(self, data: bytes) -> None:
        try:
            await self._stream.send_all(data)
        except trio.BrokenResourceError:
            pass

    async def send_eof(self) -> None:
        stream = self._unwrap_ssl()
        try:
            await stream.send_eof()
        except trio.BrokenResourceError:
            raise BrokenSocket()

    async def aclose(self) -> None:
        await self._stream.aclose()
        self._is_closed = True

    @property
    def is_closed(self) -> bool:
        return self._is_closed


class TrioQueue(Queue):
    def __init__(self, size: int) -> None:
        self._send_channel, self._receive_channel = trio.open_memory_channel[Any](size)

    async def get(self) -> Any:
        return await self._receive_channel.receive()

    async def put(self, item: Any) -> None:
        try:
            await self._send_channel.send(item)
        except (trio.BrokenResourceError, trio.ClosedResourceError):
            pass  # Already closed.

    async def aclose(self) -> None:
        try:
            await self._receive_channel.aclose()
        except trio.ClosedResourceError:
            pass  # Already closed.

        try:
            await self._send_channel.aclose()
        except trio.ClosedResourceError:
            pass  # Already closed.


class TrioListener(AsyncListener):
    def __init__(self, listener: trio.abc.Listener) -> None:
        self._listener = listener

    def _unwrap_ssl(self) -> trio.SocketListener:
        listener = self._listener
        # Unwrap SSL.
        while isinstance(listener, trio.SSLListener):
            listener = listener.transport_listener
        assert isinstance(listener, trio.SocketListener)
        return listener

    @property
    def socket(self) -> socket.SocketType:
        listener = self._unwrap_ssl()
        return listener.socket


class TrioTaskHandle(TaskHandle):
    def __init__(self, cancel_scope: trio.CancelScope) -> None:
        self._cancel_scope = cancel_scope

    async def cancel(self) -> None:
        self._cancel_scope.cancel()


class TrioBackend(AsyncBackend):
    def create_event(self) -> Event:
        return TrioEvent()

    def create_queue(self, size: int) -> Queue:
        return TrioQueue(size)

    async def sleep(self, seconds: float) -> None:
        await trio.sleep(seconds)

    def run(self, async_fn: Callable, *args: Any) -> None:
        trio.run(async_fn, *args)

    async def move_on_after(
        self, seconds: float, async_fn: Callable, *args: Any
    ) -> None:
        with trio.move_on_after(seconds):
            await async_fn(*args)

    @asynccontextmanager
    async def start_soon(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncIterator[None]:
        async with trio.open_nursery() as nursery:
            nursery.start_soon(async_fn, *args)
            yield
            if cancel_on_exit:
                nursery.cancel_scope.cancel()

    @asynccontextmanager
    async def start(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncIterator[Any]:
        async with trio.open_nursery() as nursery:
            task_status = self.create_task_status()
            async_fn = functools.partial(async_fn, task_status=task_status)
            nursery.start_soon(async_fn, *args)
            value = await task_status.get_value()
            yield value
            if cancel_on_exit:
                nursery.cancel_scope.cancel()

    async def call_later(
        self,
        seconds: float,
        async_fn: Callable,
        *args: Any,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        cancel_scope = trio.CancelScope()
        await task_status.started(TrioTaskHandle(cancel_scope))
        with cancel_scope:
            await trio.sleep(seconds)
            cancel_scope.shield = True
            await async_fn()

    async def serve_tcp(
        self,
        handler: Callable[[AsyncSocket, ServerState, Config], Awaitable[None]],
        state: ServerState,
        config: Config,
        *,
        sockets: List[socket.SocketType] = None,
        wait_close: Callable,
        on_close: Callable = None,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        async def trio_handler(stream: trio.SocketStream) -> None:
            sock = TrioSocket(stream)
            await handler(sock, state, config)

        async with trio.open_nursery() as nursery:
            listeners: Sequence[trio.abc.Listener] = []

            if sockets is not None:
                # Explicitly passed a list of open sockets.
                # (We need to wrap them around the trio equivalents.)
                trio_sockets = []
                for sock in sockets:
                    sock.listen(config.backlog)
                    trio_socket = trio.socket.fromfd(
                        sock.fileno(), sock.family, sock.type
                    )
                    trio_sockets.append(trio_socket)
                listeners = [trio.SocketListener(sock) for sock in trio_sockets]

            elif config.fd is not None:
                # Use an existing socket, from a file descriptor.
                sock = trio.socket.fromfd(config.fd, socket.AF_UNIX, socket.SOCK_STREAM)
                listeners = [trio.SocketListener(sock)]

            elif config.uds is not None:
                # Create a socket using UNIX domain socket.
                # XXX: trio does not provide highlevel support for UDS servers yet.
                # See: https://github.com/python-trio/trio/issues/279
                # This may land soon-ish, though.
                # See: https://github.com/python-trio/trio/pull/1433
                # Use the API proposed in the RFC above as a draft.
                listeners = await trio.open_unix_listeners(  # type: ignore
                    config.uds, backlog=config.backlog
                )

            else:
                # Standard case. Create a socket from a host/port pair.
                listeners = await trio.open_tcp_listeners(
                    config.port, host=config.host, backlog=config.backlog
                )

            if config.ssl:
                listeners = [
                    trio.SSLListener(listener, config.ssl, https_compatible=False)
                    for listener in listeners
                ]

            listeners = await nursery.start(
                trio.serve_listeners, trio_handler, listeners
            )
            value = [TrioListener(listener) for listener in listeners]
            await task_status.started(value)

            await wait_close()

            # Run any custom shutdown behavior.
            if on_close is not None:
                await on_close()

            # Connections are properly closed, we can go ahead and hard-stop
            # the server.
            nursery.cancel_scope.cancel()

    async def listen_signals(
        self, *signals: signal.Signals, handler: Callable[[], Awaitable[None]]
    ) -> None:
        with trio.open_signal_receiver(*signals) as signal_receiver:
            async for _ in signal_receiver:
                await handler()
