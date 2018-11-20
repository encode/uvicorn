import asyncio
import logging


STATE_TRANSITION_ERROR = 'Got invalid state transition on lifespan protocol.'


class Lifespan:
    def __init__(self, app, logger=None, startup_timeout=10, shutdown_timeout=10):
        self.logger = logger or logging.getLogger("uvicorn")
        self.startup_timeout = startup_timeout
        self.shutdown_timeout = shutdown_timeout
        self.startup_event = asyncio.Event()
        self.shutdown_event = asyncio.Event()
        self.receive_queue = asyncio.Queue()
        try:
            self.asgi = app({'type': 'lifespan'})
        except BaseException as exc:
            self.asgi = None

    @property
    def is_enabled(self):
        return self.asgi is not None

    async def run(self):
        assert self.is_enabled
        try:
            await self.asgi(self.receive, self.send)
        except BaseException as exc:
            msg = "Exception in 'lifespan' protocol\n"
            self.logger.debug(msg, exc_info=exc)
            self.asgi = None
        finally:
            self.startup_event.set()
            self.shutdown_event.set()

    async def send(self, message):
        if message['type'] == 'lifespan.startup.complete':
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()
        elif message['type'] == 'lifespan.shutdown.complete':
            assert self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.shutdown_event.is_set(), STATE_TRANSITION_ERROR
            self.shutdown_event.set()
        else:
            error = 'Got invalid message type on lifespan protocol "%s"'
            raise RuntimeError(error % message['type'])

    async def receive(self):
        message = await self.receive_queue.get()
        return message

    async def wait_startup(self):
        await self.receive_queue.put({'type': 'lifespan.startup'})
        await asyncio.wait_for(self.startup_event.wait(), timeout=self.startup_timeout)

    async def wait_shutdown(self):
        await self.receive_queue.put({'type': 'lifespan.shutdown'})
        await asyncio.wait_for(self.shutdown_event.wait(), timeout=self.shutdown_timeout)
