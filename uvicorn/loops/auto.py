def auto_loop_setup(reload: bool = False) -> None:
    try:
        import uvloop  # noqa

        assert (
            uvloop.__version__ >= "0.14.0"
        ), "Uvicorn requires uvloop version 0.14.0 or higher"
    except ImportError:  # pragma: no cover
        from uvicorn.loops.asyncio import asyncio_setup as loop_setup

        loop_setup(reload=reload)
    else:  # pragma: no cover
        from uvicorn.loops.uvloop import uvloop_setup

        uvloop_setup(reload=reload)
