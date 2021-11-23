import asyncio
from typing import Any

import uvloop


def uvloop_setup(**_: Any) -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
