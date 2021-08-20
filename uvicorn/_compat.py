"""
This module backports `asyncio.run` to Python 3.6.
You can check the original implementation on:
https://github.com/python/cpython/blob/3.7/Lib/asyncio/runners.py
"""
import sys

__all__ = ("run", "get_running_loop", "all_tasks")

if sys.version_info >= (3, 7):
    from asyncio import all_tasks, get_running_loop, run
else:
    from asyncio import AbstractEventLoop, Task, coroutines, events, futures, tasks
    from typing import Any, Coroutine, Optional, Set, TypeVar

    _T = TypeVar("_T")

    def get_running_loop() -> AbstractEventLoop:
        """Return the running event loop.  Raise a RuntimeError if there is none.
        This function is thread-specific.
        """
        # NOTE: this function is implemented in C (see _asynciomodule.c)
        loop = events._get_running_loop()
        if loop is None:
            raise RuntimeError("no running event loop")
        return loop

    def _get_loop(fut: futures.Future) -> AbstractEventLoop:
        return fut._loop

    def all_tasks(loop: Optional[AbstractEventLoop] = None) -> Set[Task]:
        """Return a set of all tasks for the loop."""
        if loop is None:
            loop = get_running_loop()
        # Looping over a WeakSet (_all_tasks) isn't safe as it can be updated
        # from another thread while we do so. Therefore we cast it to list
        # prior to filtering. The list cast itself requires iteration, so we
        # repeat it several times ignoring RuntimeErrors (which are not very
        # likely to occur). See issues 34970 and 36607 for details.
        i = 0
        while True:
            try:
                tasks = list(Task._all_tasks)  # type: ignore[attr-defined]
            except RuntimeError:
                i += 1
                if i >= 1000:
                    raise
            else:
                break
        return {t for t in tasks if _get_loop(t) is loop and not t.done()}

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
        to_cancel = all_tasks(loop)
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
