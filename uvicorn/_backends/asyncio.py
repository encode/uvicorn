import asyncio
from typing import Awaitable, Callable

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


class Queue(AsyncQueue[T]):
    def __init__(self) -> None:
        self._queue: "asyncio.Queue[T]" = asyncio.Queue()

    async def get(self) -> T:
        return await self._queue.get()

    async def put(self, item: T) -> None:
        await self._queue.put(item)


class AsyncioBackend(AsyncBackend):
    def create_event(self) -> AsyncEvent:
        return Event()

    def create_queue(self) -> AsyncQueue:
        return Queue()

    async def unsafe_spawn_task(self, async_fn: Callable[[], Awaitable[None]]) -> None:
        loop = asyncio.get_event_loop()
        loop.create_task(async_fn())
