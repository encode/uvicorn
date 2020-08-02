from uvicorn import Config


class LifespanOff:
    def __init__(self, config: Config) -> None:
        self.should_exit = False

    async def startup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass
