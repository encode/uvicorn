def auto_loop_setup(use_subprocess: bool = False) -> None:
    try:
        import uvloop  # noqa
    except ImportError:  # pragma: no cover
        from uvicorn.loops.asyncio import asyncio_setup as loop_setup
    else:  # pragma: no cover
        from uvicorn.loops.uvloop import uvloop_setup as loop_setup

    loop_setup(use_subprocess=use_subprocess)
