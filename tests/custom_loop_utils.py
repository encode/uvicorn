from __future__ import annotations

import asyncio
from asyncio import AbstractEventLoop


class CustomLoop(asyncio.SelectorEventLoop):
    pass
