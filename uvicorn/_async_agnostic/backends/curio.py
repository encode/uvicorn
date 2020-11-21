import functools
import signal
import socket
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, List, Optional, Tuple

import curio

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


class CurioEvent(Event):
    def __init__(self) -> None:
        # TODO: consider curio.UniversalEvent
        self._event = curio.Event()

    async def set(self) -> None:
        await self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def clear(self) -> None:
        self._event.clear()


class CurioSocket(AsyncSocket):
    def __init__(self, sock: curio.io.Socket, is_ssl: bool) -> None:
        self._sock = sock
        self._stream = sock.as_stream()
        self._is_closed = False
        self._is_ssl = is_ssl

    def get_local_addr(self) -> Optional[Tuple[str, int]]:
        return get_sock_local_addr(self._sock)

    def get_remote_addr(self) -> Optional[Tuple[str, int]]:
        return get_sock_remote_addr(self._sock)

    @property
    def is_ssl(self) -> bool:
        return self._is_ssl

    async def read(self, n: int) -> bytes:
        try:
            return await self._stream.receive_some(n)
        except ValueError:  # TODO
            return b""

    async def write(self, data: bytes) -> None:
        try:
            await self._stream.send_all(data)
        except ValueError:  # TODO
            pass

    async def send_eof(self) -> None:
        try:
            await self._sock.shutdown("SHUT_RD")
        except ValueError:  # TODO
            raise BrokenSocket()

    async def aclose(self) -> None:
        await self._sock.close()
        self._is_closed = True

    @property
    def is_closed(self) -> bool:
        return self._is_closed


class CurioQueue(Queue):
    def __init__(self, size: int) -> None:
        self._queue = curio.Queue(size)

    async def get(self) -> Any:
        return await self._queue.get()

    async def put(self, item: Any) -> None:
        await self._queue.put(item)

    async def aclose(self) -> None:
        pass


class CurioListener(AsyncListener):
    def __init__(self, sock: socket.SocketType) -> None:
        self._sock = sock

    @property
    def socket(self) -> socket.SocketType:
        return self._sock


class CurioTaskHandle(TaskHandle):
    def __init__(self, cancel_event: curio.Event) -> None:
        self._cancel_event = cancel_event

    async def cancel(self) -> None:
        await self._cancel_event.set()


class CurioBackend(AsyncBackend):
    def create_event(self) -> Event:
        return CurioEvent()

    def create_queue(self, size: int) -> Queue:
        return CurioQueue(size)

    async def sleep(self, seconds: float) -> None:
        await curio.sleep(seconds)

    def run(self, async_fn: Callable, *args: Any) -> None:
        curio.run(async_fn, *args)

    async def move_on_after(
        self, seconds: float, async_fn: Callable, *args: Any
    ) -> None:
        async with curio.ignore_after(seconds):
            await async_fn(*args)

    @asynccontextmanager
    async def start_soon(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncIterator[None]:
        async with curio.TaskGroup() as g:
            task = await g.spawn(async_fn, *args)
            yield

            if cancel_on_exit:
                await task.cancel()
            else:
                await task.wait()

            try:
                task.result
            except curio.TaskCancelled:
                pass

    @asynccontextmanager
    async def start(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncIterator[Any]:
        async with curio.TaskGroup() as g:
            task_status = self.create_task_status()
            async_fn = functools.partial(async_fn, task_status=task_status)
            task = await g.spawn(async_fn, *args)
            value = await task_status.get_value()
            yield value

            if cancel_on_exit:
                await task.cancel()
            else:
                await task.wait()

            try:
                task.result
            except curio.TaskCancelled:
                pass

    async def call_later(
        self,
        seconds: float,
        async_fn: Callable,
        *args: Any,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        cancel_event = curio.Event()
        await task_status.started(CurioTaskHandle(cancel_event))

        async with curio.TaskGroup(wait=any) as g:
            await g.spawn(curio.sleep, seconds)
            await g.spawn(cancel_event.wait)

        if cancel_event.is_set():
            return

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
        async def client_connected_task(csock: curio.io.Socket) -> None:
            sock = CurioSocket(csock, is_ssl=bool(config.ssl))
            await handler(sock, state, config)

        async with curio.TaskGroup() as g:
            if sockets is not None:
                # Explicitly passed a list of open sockets.
                listener_sockets = sockets

            elif config.fd is not None:
                # Use an existing socket, from a file descriptor.
                sock = socket.fromfd(config.fd, socket.AF_UNIX, socket.SOCK_STREAM)
                listener_sockets = [sock]

            elif config.uds is not None:
                # Create a socket using UNIX domain socket.
                sock = curio.unix_server_socket(config.uds, backlog=config.backlog)

            else:
                # Standard case. Create a socket from a host/port pair.
                sock = curio.tcp_server_socket(
                    config.host, config.port, backlog=config.backlog
                )

            for sock in listener_sockets:
                run_server = functools.partial(curio.run_server, ssl=config.ssl)
                await g.spawn(run_server, sock, client_connected_task)

            value = [CurioListener(sock) for sock in listener_sockets]
            await task_status.started(value)

            await wait_close()

            # Run any custom shutdown behavior.
            if on_close is not None:
                await on_close()

            # Connections are properly closed, we can go ahead and hard-stop
            # the servers.
            await g.cancel_remaining()

    async def listen_signals(
        self, *signals: signal.Signals, handler: Callable[[], Awaitable[None]]
    ) -> None:
        # https://curio.readthedocs.io/en/latest/howto.html#how-do-you-catch-signals
        signal_event = curio.UniversalEvent()

        def wrapped_handler(*args: Any) -> None:
            signal_event.set()

        for sig in signals:
            signal.signal(sig, wrapped_handler)

        while True:
            await signal_event.wait()
            signal_event.clear()
            await handler()
