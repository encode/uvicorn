import logging

from ..config import Config
from .backends.auto import AutoBackend
from .exceptions import LifespanFailure

STATE_TRANSITION_ERROR = "Got invalid state transition on lifespan protocol."
TRACE_LOG_LEVEL = 5


class Lifespan:
    def __init__(self, config: Config) -> None:
        if not config.loaded:
            config.load()
        self._config = config
        self._logger = logging.getLogger("uvicorn.error")
        self._backend = AutoBackend()
        self._startup_event = self._backend.create_event()
        self._shutdown_event = self._backend.create_event()
        self._receive_queue = self._backend.create_queue(0)
        self._mode = config.lifespan
        self._supported = self._mode in ("on", "auto")

    async def startup(self) -> None:
        if not self._supported:
            self._logger.log(TRACE_LOG_LEVEL, "lifespan startup skipped")
            return

        self._logger.info("Waiting for application startup.")
        await self._receive_queue.put({"type": "lifespan.startup"})
        await self._startup_event.wait()
        self._logger.info("Application startup complete.")

    async def shutdown(self) -> None:
        if not self._supported:
            self._logger.log(TRACE_LOG_LEVEL, "lifespan shutdown skipped")
            return

        self._logger.info("Waiting for application shutdown.")
        await self._receive_queue.put({"type": "lifespan.shutdown"})
        await self._shutdown_event.wait()
        self._logger.info("Application shutdown complete.")

    async def main(self) -> None:
        if not self._supported:
            self._logger.log(TRACE_LOG_LEVEL, "lifespan main skipped")
            return

        scope = {
            "type": "lifespan",
            "asgi": {"version": self._config.asgi_version, "spec_version": "2.0"},
        }

        app = self._config.loaded_app

        try:
            await app(scope, self._asgi_receive, self._asgi_send)
        except LifespanFailure:
            self._logger.error("Exception in 'lifespan' protocol")
            raise  # Lifespan failures should stop the server.
        except Exception:
            self._logger.info("ASGI 'lifespan' protocol appears unsupported.")
            self._supported = False
            if self._mode == "on":
                raise
        finally:
            await self._startup_event.set()
            await self._shutdown_event.set()
            await self._receive_queue.aclose()

    async def _asgi_receive(self) -> dict:
        return await self._receive_queue.get()

    async def _asgi_send(self, message: dict) -> None:
        assert message["type"] in (
            "lifespan.startup.complete",
            "lifespan.startup.failed",
            "lifespan.shutdown.complete",
            "lifespan.shutdown.failed",
        ), message["type"]

        if message["type"] == "lifespan.startup.complete":
            assert not self._startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self._shutdown_event.is_set(), STATE_TRANSITION_ERROR
            await self._startup_event.set()

        elif message["type"] == "lifespan.startup.failed":
            assert not self._startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self._shutdown_event.is_set(), STATE_TRANSITION_ERROR
            await self._startup_event.set()
            raise LifespanFailure(message.get("message", ""))

        elif message["type"] == "lifespan.shutdown.complete":
            assert self._startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self._shutdown_event.is_set(), STATE_TRANSITION_ERROR
            await self._shutdown_event.set()

        else:
            assert message["type"] == "lifespan.shutdown.failed"
            assert self._startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self._shutdown_event.is_set(), STATE_TRANSITION_ERROR
            await self._shutdown_event.set()
            raise LifespanFailure(message.get("message", ""))
