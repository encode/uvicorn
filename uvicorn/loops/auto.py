from typing import Optional


def auto_loop_setup(reload: bool = False, workers: Optional[int] = None) -> None:
    try:
        import uvloop  # noqa
    except ImportError:  # pragma: no cover
        from uvicorn.loops.asyncio import asyncio_setup as loop_setup

        loop_setup(reload=reload, workers=workers)
    else:  # pragma: no cover
        from uvicorn.loops.uvloop import uvloop_setup

        uvloop_setup(reload=reload, workers=workers)
