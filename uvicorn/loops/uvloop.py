import asyncio

import uvloop

from uvicorn._utils import version_parse

if version_parse(uvloop.__version__) < version_parse("0.14.0"):
    raise RuntimeError(
        f'"uvloop" version {uvloop.__version__} was found.\n'
        'Uvicorn requires "uvloop" version 0.14.0 or higher.'
    )


def uvloop_setup(reload: bool = False) -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
