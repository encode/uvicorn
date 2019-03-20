class LifespanOff:
    def __init__(self, config):
        self.should_exit = False

    async def startup(self):
        pass

    async def shutdown(self):
        pass
