from typing import ContextManager

import uvloop

from ._policy_cmgr import policy_cmgr


def uvloop_setup() -> ContextManager[None]:
    return policy_cmgr(uvloop.EventLoopPolicy)
