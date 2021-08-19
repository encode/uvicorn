from typing import ContextManager


def auto_loop_setup() -> ContextManager[None]:
    try:
        import uvloop  # noqa
    except ImportError:  # pragma: no cover
        from uvicorn.loops.asyncio import asyncio_setup as loop_setup

        return loop_setup()
    else:  # pragma: no cover
        from uvicorn.loops.uvloop import uvloop_setup

        return uvloop_setup()
