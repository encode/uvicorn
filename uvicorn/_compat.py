"""
This module backports `asyncio.run` to Python 3.6.
You can check the original implementation on:
https://github.com/python/cpython/blob/3.7/Lib/asyncio/runners.py
"""
import sys

__all__ = ("run",)

if sys.version_info >= (3, 7):
    from asyncio import run
else:
    from asyncio import AbstractEventLoop, coroutines, events, tasks
    from typing import Any, Coroutine, TypeVar

    _T = TypeVar("_T")

    def run(main: Coroutine[Any, Any, _T], *, debug: bool = False) -> _T:
        """Execute the coroutine and return the result.
        This function runs the passed coroutine, taking care of
        managing the asyncio event loop and finalizing asynchronous
        generators.
        This function cannot be called when another asyncio event loop is
        running in the same thread.
        If debug is True, the event loop will be run in debug mode.
        This function always creates a new event loop and closes it at the end.
        It should be used as a main entry point for asyncio programs, and should
        ideally only be called once.
        Example:
            async def main():
                await asyncio.sleep(1)
                print('hello')
            asyncio.run(main())
        """
        if events._get_running_loop() is not None:
            raise RuntimeError(
                "asyncio.run() cannot be called from a running event loop"
            )

        if not coroutines.iscoroutine(main):
            raise ValueError("a coroutine was expected, got {!r}".format(main))

        loop = events.new_event_loop()
        try:
            events.set_event_loop(loop)
            loop.set_debug(debug)
            return loop.run_until_complete(main)
        finally:
            try:
                _cancel_all_tasks(loop)
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                events.set_event_loop(None)
                loop.close()

    def _cancel_all_tasks(loop: AbstractEventLoop) -> None:
        to_cancel = tasks.all_tasks(loop)  # type: ignore[attr-defined]
        if not to_cancel:
            return

        for task in to_cancel:
            task.cancel()

        loop.run_until_complete(
            tasks.gather(*to_cancel, loop=loop, return_exceptions=True)
        )

        for task in to_cancel:
            if task.cancelled():
                continue
            if task.exception() is not None:
                loop.call_exception_handler(
                    {
                        "message": "unhandled exception during asyncio.run() shutdown",
                        "exception": task.exception(),
                        "task": task,
                    }
                )
