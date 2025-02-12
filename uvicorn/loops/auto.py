from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable


def auto_loop_factory(use_subprocess: bool = False) -> Callable[[], asyncio.AbstractEventLoop]:  # pragma: no cover
    try:
        import uvloop  # noqa
    except ImportError:  # pragma: no cover
        pass
    except AttributeError:  # pragma: no cover
        if sys.version_info < (3, 14):
            raise
    else:  # pragma: no cover
        from uvicorn.loops.uvloop import uvloop_loop_factory

        return uvloop_loop_factory(use_subprocess=use_subprocess)

    from uvicorn.loops.asyncio import asyncio_loop_factory as loop_factory

    return loop_factory(use_subprocess=use_subprocess)
