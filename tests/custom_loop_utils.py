from __future__ import annotations

import asyncio
from asyncio import AbstractEventLoop


class CustomLoop(asyncio.SelectorEventLoop):
    pass


def custom_loop_factory(use_subprocess: bool) -> type[AbstractEventLoop]:
    return CustomLoop
