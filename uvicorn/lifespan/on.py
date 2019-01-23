import asyncio
import sys

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocol."


class LifespanOn:
    def __init__(self, config):
        if not config.loaded:
            config.load()

        self.config = config
        self.logger = config.logger_instance
        self.timeout_startup = 10
        self.timeout_shutdown = 10
        self.startup_event = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        self.receive_queue = asyncio.Queue()
        self.error_occured = False

    async def run(self):
        try:
            app_instance = self.config.loaded_app({"type": "lifespan"})
            await app_instance(self.receive, self.send)
        except BaseException as exc:
            msg = "Exception in 'lifespan' protocol\n"
            self.logger.error(msg, exc_info=exc)
            self.asgi = None
            self.error_occured = True
        finally:
            self.startup_event.set()
            self.shutdown_event.set()

    async def startup(self):
        self.logger.info("Waiting for application startup.")
        await self.receive_queue.put({"type": "lifespan.startup"})

        try:
            await asyncio.wait_for(
                self.startup_event.wait(), timeout=self.timeout_startup
            )
        except asyncio.TimeoutError as exc:
            self.logger.error("Application startup timed out. Exiting.")
            sys.exit(1)

        if self.error_occured:
            self.logger.error("Application startup failed. Exiting.")
            sys.exit(1)

    async def shutdown(self):
        self.logger.info("Waiting for application shutdown.")
        await self.receive_queue.put({"type": "lifespan.shutdown"})

        try:
            await asyncio.wait_for(
                self.shutdown_event.wait(), timeout=self.timeout_shutdown
            )
        except asyncio.TimeoutError as exc:
            self.logger.error("Application shutdown timed out.")

    async def send(self, message):
        if message["type"] == "lifespan.startup.complete":
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()
        elif message["type"] == "lifespan.shutdown.complete":
            assert self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.shutdown_event.set()
        else:
            error = 'Got invalid message type on lifespan protocol "%s"'
            raise RuntimeError(error % message["type"])

    async def receive(self):
        message = await self.receive_queue.get()
        return message
