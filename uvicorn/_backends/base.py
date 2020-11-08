from typing import Any, AsyncContextManager, Callable, Generic, TypeVar

T = TypeVar("T")


class AsyncEvent:
    """
    Base interface for events.
    """

    def is_set(self) -> bool:
        raise NotImplementedError  # pragma: no cover

    def set(self) -> None:
        raise NotImplementedError  # pragma: no cover

    async def wait(self) -> None:
        raise NotImplementedError  # pragma: no cover

    def clear(self) -> None:
        raise NotImplementedError  # pragma: no cover


class AsyncQueue(Generic[T]):
    """
    Base interface for FIFO queues.
    """

    async def get(self) -> T:
        raise NotImplementedError  # pragma: no cover

    async def put(self, item: T) -> None:
        raise NotImplementedError  # pragma: no cover


class AsyncBackend:
    """
    Base interface for async concurrency backends.

    Aims at abstracting away any asyncio-specific APIs.
    """

    def create_event(self) -> AsyncEvent:
        raise NotImplementedError  # pragma: no cover

    def create_queue(self) -> AsyncQueue:
        raise NotImplementedError  # pragma: no cover

    def call_soon(self, fn: Callable, *args: Any) -> None:
        raise NotImplementedError  # pragma: no cover

    def unsafe_spawn_task(self, async_fn: Callable, *args: Any) -> None:
        raise NotImplementedError  # pragma: no cover

    def run_in_background(
        self, async_fn: Callable, *args: Any
    ) -> AsyncContextManager[None]:
        raise NotImplementedError  # pragma: no cover

    async def run_sync_in_thread(self, fn: Callable, *args: Any) -> None:
        raise NotImplementedError  # pragma: no cover
