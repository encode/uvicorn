def auto_loop_setup():
    try:
        import uvloop  # noqa
    except ImportError:  # pragma: no cover
        from uvicorn.loops.asyncio import asyncio_setup as loop_setup

        loop_setup()
    else:
        from uvicorn.loops.uvloop import uvloop_setup

        uvloop_setup()
