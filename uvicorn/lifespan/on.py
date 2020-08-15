import asyncio
import logging
from asyncio import Queue

from uvicorn import Config
from uvicorn._types import LifespanReceiveMessage, LifespanScope, LifespanSendMessage

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocol."


class LifespanOn:
    def __init__(self, config: Config) -> None:
        if not config.loaded:
            config.load()

        self.config = config
        self.logger = logging.getLogger("uvicorn.error")
        self.startup_event = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        self.receive_queue: Queue = asyncio.Queue()
        self.error_occured = False
        self.startup_failed = False
        self.should_exit = False

    async def startup(self) -> None:
        self.logger.info("Waiting for application startup.")

        loop = asyncio.get_event_loop()
        loop.create_task(self.main())

        await self.receive_queue.put({"type": "lifespan.startup"})
        await self.startup_event.wait()

        if self.startup_failed or (self.error_occured and self.config.lifespan == "on"):
            self.logger.error("Application startup failed. Exiting.")
            self.should_exit = True
        else:
            self.logger.info("Application startup complete.")

    async def shutdown(self) -> None:
        if self.error_occured:
            return
        self.logger.info("Waiting for application shutdown.")
        await self.receive_queue.put({"type": "lifespan.shutdown"})
        await self.shutdown_event.wait()
        self.logger.info("Application shutdown complete.")

    async def main(self) -> None:
        try:
            app = self.config.loaded_app
            scope: LifespanScope = {
                "type": "lifespan",
                "asgi": {"version": self.config.asgi_version, "spec_version": "2.0"},
            }
            await app(scope, self.receive, self.send)
        except BaseException as exc:
            self.asgi = None
            self.error_occured = True
            if self.startup_failed:
                return
            if self.config.lifespan == "auto":
                msg = "ASGI 'lifespan' protocol appears unsupported."
                self.logger.info(msg)
            else:
                msg = "Exception in 'lifespan' protocol\n"
                self.logger.error(msg, exc_info=exc)
        finally:
            self.startup_event.set()
            self.shutdown_event.set()

    async def send(self, message: LifespanSendMessage) -> None:
        assert message["type"] in (
            "lifespan.startup.complete",
            "lifespan.startup.failed",
            "lifespan.shutdown.complete",
        )

        if message["type"] == "lifespan.startup.complete":
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()

        elif message["type"] == "lifespan.startup.failed":
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()
            self.startup_failed = True
            if message.get("message"):
                self.logger.error(message["message"])

        elif message["type"] == "lifespan.shutdown.complete":
            assert self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.shutdown_event.set()

    async def receive(self) -> LifespanReceiveMessage:
        return await self.receive_queue.get()
