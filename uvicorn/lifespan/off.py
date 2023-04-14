from typing import Any, ChainMap

from uvicorn import Config


class LifespanOff:
    def __init__(self, config: Config) -> None:
        self.should_exit = False
        self.state: ChainMap[str, Any] = ChainMap()

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
