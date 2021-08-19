import asyncio
import contextlib
import sys
from typing import ContextManager

from ._policy_cmgr import policy_cmgr


def asyncio_setup() -> ContextManager[None]:  # pragma: no cover
    if sys.version_info >= (3, 8) and sys.platform == "win32":
        return policy_cmgr(asyncio.WindowsSelectorEventLoopPolicy)
    return contextlib.nullcontext(None)
