import asyncio
import concurrent.futures
from typing import Any, AsyncIterator, Callable

from uvicorn._compat import asynccontextmanager

from .base import AsyncBackend, AsyncEvent, AsyncQueue, T


class Event(AsyncEvent):
    def __init__(self) -> None:
        self._event = asyncio.Event()

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self) -> None:
        self._event.set()

    async def wait(self) -> None:
        await self._event.wait()

    def clear(self) -> None:
        self._event.clear()


class Queue(AsyncQueue[T]):
    def __init__(self) -> None:
        self._queue: "asyncio.Queue[T]" = asyncio.Queue()

    async def get(self) -> T:
        return await self._queue.get()

    async def put(self, item: T) -> None:
        await self._queue.put(item)


class AsyncioBackend(AsyncBackend):
    def __init__(self) -> None:
        self._executor = concurrent.futures.ThreadPoolExecutor()
        self._loop = asyncio.get_event_loop()

    def create_event(self) -> AsyncEvent:
        return Event()

    def create_queue(self) -> AsyncQueue:
        return Queue()

    def call_soon(self, fn: Callable, *args: Any) -> None:
        self._loop.call_soon_threadsafe(fn, *args)

    def unsafe_spawn_task(self, async_fn: Callable, *args: Any) -> None:
        self._loop.create_task(async_fn())

    @asynccontextmanager
    async def run_in_background(
        self, async_fn: Callable, *args: Any
    ) -> AsyncIterator[None]:
        task = self._loop.create_task(async_fn(*args))
        try:
            yield
        finally:
            await asyncio.wait_for(task, None)

    async def run_sync_in_thread(self, fn: Callable, *args: Any) -> None:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        await self._loop.run_in_executor(executor, fn, *args)
