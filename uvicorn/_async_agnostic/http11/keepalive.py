from contextlib import AsyncExitStack
from typing import Optional

from uvicorn.config import Config

from ..backends.auto import AutoBackend
from ..backends.base import TaskHandle, TaskStatus
from .connection import HTTP11Connection


class KeepAlive:
    def __init__(self, conn: HTTP11Connection, config: Config) -> None:
        self._conn = conn
        self._config = config
        self._backend = AutoBackend()
        self._task_handle: Optional[TaskHandle] = None
        self._exit_stack = AsyncExitStack()

    async def schedule(self) -> None:
        assert self._task_handle is None

        self._task_handle = await self._exit_stack.enter_async_context(
            self._backend.start(
                self._trigger_shutdown_after_expiry,
                cancel_on_exit=True,
            ),
        )

    async def _trigger_shutdown_after_expiry(
        self, *, task_status: TaskStatus = TaskStatus.IGNORED
    ) -> None:
        timeout = self._config.timeout_keep_alive
        self._conn.trace("keep-alive expiry scheduled in %d seconds", timeout)
        await self._backend.wait_then_call(
            timeout,
            async_fn=self._trigger_shutdown,
            task_status=task_status,
        )

    async def _trigger_shutdown(self) -> None:
        self._conn.trace("keep-alive expired")
        await self._conn.trigger_shutdown()

    async def reset(self) -> None:
        if self._task_handle is not None:
            self._conn.trace("keep-alive reset")
            await self._task_handle.cancel()
            self._task_handle = None

    async def aclose(self) -> None:
        await self._exit_stack.aclose()
        self._conn.trace("keep-alive expiry cancelled")
