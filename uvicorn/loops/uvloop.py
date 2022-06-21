import asyncio
from typing import Optional

import uvloop


def uvloop_setup(reload: bool = False, workers: Optional[int] = None) -> None:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
