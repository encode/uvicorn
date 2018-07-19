def auto_loop_setup():
    try:
        import uvloop
    except ImportError:  # pragma: no cover
        from uvicorn.loops.asyncio import asyncio_setup

        return asyncio_setup()
    else:
        from uvicorn.loops.uvloop import uvloop_setup

        return uvloop_setup()
