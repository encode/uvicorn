from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from typing import TypeVar

_T = TypeVar("_T")

logger = logging.getLogger("uvicorn.error")


def asyncio_loop_factory(use_subprocess: bool = False) -> Callable[[], asyncio.AbstractEventLoop]:
    if sys.platform == "win32" and not use_subprocess:
        return asyncio.ProactorEventLoop
    return asyncio.SelectorEventLoop
