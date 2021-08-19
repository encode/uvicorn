import asyncio
import sys
from typing import ContextManager

from ._policy_cmgr import policy_cmgr

if sys.version_info < (3, 7):
    from contextlib2 import nullcontext
else:
    from contextlib import nullcontext


def asyncio_setup() -> ContextManager[None]:  # pragma: no cover
    if sys.version_info >= (3, 8) and sys.platform == "win32":
        return policy_cmgr(asyncio.WindowsSelectorEventLoopPolicy)
    return nullcontext(None)
