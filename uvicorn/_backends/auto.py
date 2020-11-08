from typing import Awaitable, Callable

import sniffio

from .base import AsyncBackend, AsyncEvent, AsyncQueue


class AutoBackend(AsyncBackend):
    @property
    def _backend(self) -> AsyncBackend:
        if not hasattr(self, "_backend_impl"):
            library = sniffio.current_async_library()
            if library == "asyncio":
                from .asyncio import AsyncioBackend

                self._backend_impl = AsyncioBackend()
            else:
                raise RuntimeError("Unknown async environment: {library}")

        return self._backend_impl

    def create_event(self) -> AsyncEvent:
        return self._backend.create_event()

    def create_queue(self) -> AsyncQueue:
        return self._backend.create_queue()

    def unsafe_spawn_task(self, async_fn: Callable[[], Awaitable[None]]) -> None:
        self._backend.unsafe_spawn_task(async_fn)
