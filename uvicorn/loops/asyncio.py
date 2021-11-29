import asyncio
import logging
import sys

logger = logging.getLogger("uvicorn.error")


def asyncio_setup(reload: bool = False) -> None:  # pragma: no cover
    if sys.version_info >= (3, 8) and sys.platform == "win32" and reload:
        logger.warning("The --reload flag should not be used in production on Windows.")
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
