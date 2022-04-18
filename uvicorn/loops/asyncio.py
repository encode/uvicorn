import asyncio
import logging
import sys

logger = logging.getLogger("uvicorn.error")


def asyncio_setup(reload: bool = False) -> None:  # pragma: no cover
    if sys.version_info >= (3, 8) and sys.platform == "win32":
        if reload:
            logger.warning(
                "The --reload flag should not be \
                used in production on Windows."
            )
        try:
            from asyncio import WindowsSelectorEventLoopPolicy
        except ImportError:
            logger.error("Can't assign a policy which doesn't exist.")
        else:
            if not isinstance(
                asyncio.get_event_loop_policy(), WindowsSelectorEventLoopPolicy
            ):
                asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())
