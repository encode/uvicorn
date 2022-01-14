from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uvicorn import Config


class LifespanOff:
    def __init__(self, config: Config) -> None:
        self.should_exit = False

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
