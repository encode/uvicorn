import asyncio
import threading

import uvloop


def uvloop_setup() -> None:
    if threading.current_thread() is threading.main_thread():
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    else:
        asyncio.set_event_loop(uvloop.new_event_loop())
