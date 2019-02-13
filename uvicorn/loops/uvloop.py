import asyncio

import uvloop


def uvloop_setup():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
