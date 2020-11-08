try:
    from contextlib import AsyncExitStack
except ImportError:  # pragma: no cover
    # Python < 3.7
    from async_exit_stack import AsyncExitStack  # type: ignore

try:
    from contextlib import asynccontextmanager
except ImportError:  # pragma: no cover
    # Python < 3.7
    from async_generator import asynccontextmanager  # type: ignore


__all__ = [
    "AsyncExitStack",
    "asynccontextmanager",
]
