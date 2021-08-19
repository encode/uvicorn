import asyncio
import contextlib
import threading
from typing import Generator, Type


@contextlib.contextmanager
def policy_cmgr(
    policy_type: Type[asyncio.AbstractEventLoopPolicy],
) -> Generator[None, None, None]:
    old_policy = asyncio.get_event_loop_policy()
    if type(old_policy) is policy_type:
        yield
        return

    if threading.current_thread() != threading.main_thread():
        raise AssertionError(
            f"Your current eventloop policy is {type(old_policy)} "
            f"however {policy_type} was requested and uvicorn "
            "cannot safely change policy off main thread "
            "call asyncio.set_event_loop_policy(ChosenPolicy()) on the main "
            "thread instead"
        )

    new_policy = policy_type()
    asyncio.set_event_loop_policy(new_policy)
    try:
        yield
    finally:
        assert asyncio.get_event_loop_policy() is new_policy
        asyncio.set_event_loop_policy(old_policy)
