import asyncio
import os
import platform
import signal
import socket
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable, List, Optional, Tuple

from ...config import Config
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

HIGH_WATER_LIMIT = 2 ** 16


class AsyncioEvent(Event):
    def __init__(self) -> None:
        self._event = asyncio.Event()

    async def set(self) -> None:
        self._event.set()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def clear(self) -> None:
        self._event.clear()


class AsyncioQueue(Queue):
    def __init__(self, size: int) -> None:
        self._queue: "asyncio.Queue[Any]" = asyncio.Queue(size)
        self._closed = False

    async def get(self) -> Any:
        if self._closed:
            raise RuntimeError("Queue closed")
        return await self._queue.get()

    async def put(self, item: Any) -> None:
        await self._queue.put(item)

    async def aclose(self) -> None:
        self._closed = True


class AsyncioSocket(AsyncSocket):
    def __init__(
        self, stream_reader: asyncio.StreamReader, stream_writer: asyncio.StreamWriter
    ) -> None:
        self._stream_reader = stream_reader
        self._stream_writer = stream_writer

    def get_local_addr(self) -> Optional[Tuple[str, int]]:
        sock = self._stream_writer.get_extra_info("socket")
        if sock is not None:
            return get_sock_local_addr(sock)

        info = self._stream_writer.get_extra_info("peername")
        try:
            host, port = info
        except ValueError:
            return None
        else:
            return str(host), int(port)

    def get_remote_addr(self) -> Optional[Tuple[str, int]]:
        sock = self._stream_writer.get_extra_info("socket")
        if sock is not None:
            return get_sock_remote_addr(sock)

        info = self._stream_writer.get_extra_info("peername")
        try:
            host, port = info
        except ValueError:
            return None
        else:
            return str(host), int(port)

    @property
    def is_ssl(self) -> bool:
        transport = self._stream_writer.transport
        return bool(transport.get_extra_info("sslcontext"))

    async def read(self, n: int) -> bytes:
        return await self._stream_reader.read(n)

    async def write(self, data: bytes) -> None:
        self._stream_writer.write(data)
        await self._stream_writer.drain()

    async def send_eof(self) -> None:
        try:
            self._stream_writer.write_eof()
        except (NotImplementedError, OSError, RuntimeError):
            pass  # Likely SSL connection

    async def aclose(self) -> None:
        try:
            self._stream_writer.close()
            await self._stream_writer.wait_closed()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Already closed

    @property
    def is_closed(self) -> bool:
        return self._stream_writer.is_closing()


class AsyncioListener(AsyncListener):
    def __init__(self, sock: socket.SocketType) -> None:
        self._sock = sock

    @property
    def socket(self) -> socket.SocketType:
        return self._sock


class AsyncioTaskHandle(TaskHandle):
    def __init__(self, cancel_event: asyncio.Event) -> None:
        self._cancel_event = cancel_event

    async def cancel(self) -> None:
        self._cancel_event.set()


class AsyncioBackend(AsyncBackend):
    def create_event(self) -> Event:
        return AsyncioEvent()

    def create_queue(self, size: int) -> Queue:
        return AsyncioQueue(size)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def _get_event_loop(self) -> asyncio.AbstractEventLoop:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # We're probably in a new thread.
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop

    def run(self, async_fn: Callable, *args: Any) -> None:
        loop = self._get_event_loop()
        loop.run_until_complete(async_fn(*args))

    async def move_on_after(
        self, seconds: float, async_fn: Callable, *args: Any
    ) -> None:
        try:
            await asyncio.wait_for(async_fn(*args), seconds)
        except asyncio.TimeoutError:
            return

    @asynccontextmanager
    async def start_soon(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncIterator[None]:
        loop = self._get_event_loop()
        task = loop.create_task(async_fn(*args))
        try:
            yield
        finally:
            if cancel_on_exit:
                task.cancel()
            else:
                await task

    @asynccontextmanager
    async def start(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncIterator[Any]:
        loop = self._get_event_loop()
        task_status = self.create_task_status()
        task = loop.create_task(async_fn(*args, task_status=task_status))
        try:
            value = await task_status.get_value()
            yield value
        finally:
            if cancel_on_exit:
                task.cancel()
            else:
                await task

    async def call_later(
        self,
        seconds: float,
        async_fn: Callable,
        *args: Any,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        cancel_event = asyncio.Event()
        await task_status.started(AsyncioTaskHandle(cancel_event))

        # Wait for the user to cancel the callback, or for the timeout to expire.
        # Be sure to clean up after asyncio.
        tasks: set = {
            asyncio.create_task(asyncio.sleep(seconds)),
            asyncio.create_task(cancel_event.wait()),
        }
        try:
            _, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        except asyncio.CancelledError:
            for task in tasks:
                task.cancel()
        else:
            for task in pending:
                task.cancel()

        if cancel_event.is_set():
            return

        await async_fn(*args)

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
        async def asyncio_handler(
            stream_reader: asyncio.StreamReader, stream_writer: asyncio.StreamWriter
        ) -> None:
            sock = AsyncioSocket(stream_reader, stream_writer)
            await handler(sock, state, config)

        servers = []

        if sockets is not None:
            # Explicitly passed a list of open sockets.

            def _win32_share_socket(sock: socket.SocketType) -> socket.SocketType:
                # Windows requires the socket be explicitly shared across
                # multiple workers (processes).
                from socket import fromshare  # type: ignore

                sock_data = sock.share(os.getpid())  # type: ignore
                return fromshare(sock_data)

            for sock in sockets:
                if config.workers > 1 and platform.system() == "Windows":
                    sock = _win32_share_socket(sock)
                server = await asyncio.start_server(
                    asyncio_handler,
                    sock=sock,
                    ssl=config.ssl,
                    backlog=config.backlog,
                )
                servers.append(server)

            listener_sockets = sockets

        elif config.fd is not None:
            # Use an existing socket, from a file descriptor.
            sock = socket.fromfd(config.fd, socket.AF_UNIX, socket.SOCK_STREAM)
            server = await asyncio.start_server(
                asyncio_handler, sock=sock, ssl=config.ssl, backlog=config.backlog
            )
            assert server.sockets is not None
            listener_sockets = server.sockets
            servers.append(server)

        elif config.uds is not None:
            # Create a socket using UNIX domain socket.
            uds_perms = 0o666
            if os.path.exists(config.uds):
                uds_perms = os.stat(config.uds).st_mode
            server = await asyncio.start_unix_server(
                asyncio_handler,
                path=config.uds,
                ssl=config.ssl,
                backlog=config.backlog,
            )
            os.chmod(config.uds, uds_perms)
            assert server.sockets is not None
            listener_sockets = server.sockets
            servers.append(server)

        else:
            # Standard case. Create a socket from a host/port pair.
            server = await asyncio.start_server(
                asyncio_handler,
                host=config.host,
                port=config.port,
                ssl=config.ssl,
                backlog=config.backlog,
            )
            assert server.sockets is not None
            listener_sockets = server.sockets
            servers.append(server)

        listeners = [AsyncioListener(sock) for sock in listener_sockets]
        await task_status.started(listeners)

        await wait_close()

        # Stop accepting new connections.
        for server in servers:
            server.close()
        for sock in sockets or []:
            sock.close()

        # Run any custom shutdown behavior.
        if on_close is not None:
            await on_close()

        for server in servers:
            await server.wait_closed()

    async def listen_signals(
        self, *signals: signal.Signals, handler: Callable[[], Awaitable[None]]
    ) -> None:
        signal_event = asyncio.Event()

        def wrapped_handler(*args: Any) -> None:
            signal_event.set()

        loop = self._get_event_loop()
        try:
            for sig in signals:
                loop.add_signal_handler(sig, wrapped_handler, sig, None)
        except NotImplementedError:
            # Windows
            for sig in signals:
                signal.signal(sig, wrapped_handler)

        while True:
            await signal_event.wait()
            signal_event.clear()
            await handler()
