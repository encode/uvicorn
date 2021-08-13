import asyncio
import sys


def asyncio_setup() -> None:  # pragma: no cover
    if sys.version_info >= (3, 8) and sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
