import signal
import socket
from typing import Any, AsyncContextManager, Awaitable, Callable, List

import sniffio

from ...config import Config
from ..state import ServerState
from .base import AsyncBackend, AsyncSocket, Event, Queue, TaskStatus


def select_async_backend(library: str) -> AsyncBackend:
    if library == "asyncio":
        from .asyncio import AsyncioBackend

        return AsyncioBackend()

    if library == "trio":
        from .trio import TrioBackend

        return TrioBackend()

    if library == "curio":
        from .curio import CurioBackend

        return CurioBackend()

    raise NotImplementedError(library)


class AutoBackend(AsyncBackend):
    @property
    def _backend(self) -> AsyncBackend:
        if not hasattr(self, "_backend_impl"):
            library = sniffio.current_async_library()
            self._backend_impl = select_async_backend(library)
        return self._backend_impl

    def create_event(self) -> Event:
        return self._backend.create_event()

    def create_queue(self, size: int) -> Queue:
        return self._backend.create_queue(size)

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)

    def run(self, async_fn: Callable, *args: Any) -> None:
        self._backend.run(async_fn)

    async def move_on_after(
        self, seconds: float, async_fn: Callable, *args: Any
    ) -> None:
        await self._backend.move_on_after(seconds, async_fn, *args)

    def start_soon(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncContextManager[None]:
        return self._backend.start_soon(async_fn, *args, cancel_on_exit=cancel_on_exit)

    def start(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncContextManager[Any]:
        return self._backend.start(async_fn, *args, cancel_on_exit=cancel_on_exit)

    async def wait_then_call(
        self,
        seconds: float,
        async_fn: Callable,
        *args: Any,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        await self._backend.wait_then_call(
            seconds, async_fn, *args, task_status=task_status
        )

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
        await self._backend.serve_tcp(
            handler,
            state,
            config,
            sockets=sockets,
            wait_close=wait_close,
            on_close=on_close,
            task_status=task_status,
        )

    async def listen_signals(
        self, *signals: signal.Signals, handler: Callable[[], Awaitable[None]]
    ) -> None:
        await self._backend.listen_signals(*signals, handler=handler)
