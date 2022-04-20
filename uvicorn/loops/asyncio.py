import asyncio
import logging
import sys
from typing import Optional

logger = logging.getLogger("uvicorn.error")


def asyncio_setup(
    reload: bool = False, workers: Optional[int] = None
) -> None:  # pragma: no cover
    if (
        sys.version_info >= (3, 8)
        and sys.platform == "win32"
        and any([reload, workers])
    ):
        if reload:
            logger.warning(
                "The --reload flag should not be used in production on Windows."
            )
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
