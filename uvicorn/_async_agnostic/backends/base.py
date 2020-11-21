import signal
import socket
from typing import Any, AsyncContextManager, Awaitable, Callable, List, Optional, Tuple

from ...config import Config
from ..state import ServerState


class Event:
    async def set(self) -> None:
        raise NotImplementedError  # pragma: no cover

    def is_set(self) -> bool:
        raise NotImplementedError  # pragma: no cover

    async def wait(self) -> None:
        raise NotImplementedError  # pragma: no cover

    def clear(self) -> None:
        raise NotImplementedError  # pragma: no cover


class Queue:
    async def get(self) -> Any:
        raise NotImplementedError  # pragma: no cover

    async def put(self, item: Any) -> None:
        raise NotImplementedError  # pragma: no cover

    async def aclose(self) -> None:
        raise NotImplementedError  # pragma: no cover


class AsyncSocket:
    def get_local_addr(self) -> Optional[Tuple[str, int]]:
        raise NotImplementedError  # pragma: no cover

    def get_remote_addr(self) -> Optional[Tuple[str, int]]:
        raise NotImplementedError  # pragma: no cover

    @property
    def is_ssl(self) -> bool:
        raise NotImplementedError  # pragma: no cover

    async def read(self, n: int) -> bytes:
        raise NotImplementedError  # pragma: no cover

    async def write(self, data: bytes) -> None:
        raise NotImplementedError  # pragma: no cover

    async def send_eof(self) -> None:
        raise NotImplementedError  # pragma: no cover

    async def aclose(self) -> None:
        raise NotImplementedError  # pragma: no cover

    @property
    def is_closed(self) -> bool:
        raise NotImplementedError  # pragma: no cover


class AsyncListener:
    @property
    def socket(self) -> socket.SocketType:
        raise NotImplementedError  # pragma: no cover


class TaskStatus:
    IGNORED: "IgnoredTaskStatus"

    def __init__(self, event: Event) -> None:
        self._value_event = event

    async def started(self, value: Any = None) -> None:
        self._value = value
        await self._value_event.set()

    async def get_value(self) -> Any:
        await self._value_event.wait()
        assert hasattr(self, "_value")
        return self._value


class TaskHandle:
    async def cancel(self) -> None:
        raise NotImplementedError  # pragma: no cover


class IgnoredTaskStatus(TaskStatus):
    def __init__(self) -> None:
        super().__init__(None)  # type: ignore

    async def started(self, value: Any = None) -> None:
        pass

    async def get_value(self) -> Any:
        return None


TaskStatus.IGNORED = IgnoredTaskStatus()


class AsyncBackend:
    def create_event(self) -> Event:
        raise NotImplementedError  # pragma: no cover

    def create_queue(self, size: int) -> Queue:
        raise NotImplementedError  # pragma: no cover

    def create_task_status(self) -> TaskStatus:
        event = self.create_event()
        return TaskStatus(event)

    async def sleep(self, seconds: float) -> None:
        raise NotImplementedError  # pragma: no cover

    def run(self, async_fn: Callable, *args: Any) -> None:
        raise NotImplementedError  # pragma: no cover

    async def move_on_after(
        self, seconds: float, async_fn: Callable, *args: Any
    ) -> None:
        raise NotImplementedError  # pragma: no cover

    def start_soon(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncContextManager[None]:
        raise NotImplementedError  # pragma: no cover

    def start(
        self, async_fn: Callable, *args: Any, cancel_on_exit: bool = False
    ) -> AsyncContextManager[Any]:
        raise NotImplementedError  # pragma: no cover

    async def call_later(
        self,
        seconds: float,
        async_fn: Callable,
        *args: Any,
        task_status: TaskStatus = TaskStatus.IGNORED,
    ) -> None:
        raise NotImplementedError  # pragma: no cover

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
        raise NotImplementedError  # pragma: no cover

    async def listen_signals(
        self, *signals: signal.Signals, handler: Callable[[], Awaitable[None]]
    ) -> None:
        raise NotImplementedError  # pragma: no cover
