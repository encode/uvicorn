import asyncio
import logging
import traceback


STATE_TRANSITION_ERROR = 'Got invalid state transition on lifespan protocol.'


class Lifespan:
    def __init__(self, app, logger=None, startup_timeout=10, cleanup_timeout=10):
        self.logger = logger or logging.getLogger("uvicorn")
        self.startup_timeout = startup_timeout
        self.cleanup_timeout = cleanup_timeout
        self.startup_event = asyncio.Event()
        self.cleanup_event = asyncio.Event()
        self.receive_queue = asyncio.Queue()
        try:
            self.asgi = app({'type': 'lifespan'})
        except:
            self.asgi = None

    @property
    def is_enabled(self):
        return self.asgi is not None

    async def run(self):
        assert self.is_enabled
        try:
            await self.asgi(self.receive, self.send)
        except:
            msg = "Exception in 'lifespan' protocol\n%s"
            traceback_text = "".join(traceback.format_exc())
            self.logger.debug(msg, traceback_text)
            self.asgi = None
        finally:
            self.startup_event.set()
            self.cleanup_event.set()

    async def send(self, message):
        if message['type'] == 'lifespan.startup.complete':
            assert not self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.cleanup_event.is_set(), STATE_TRANSITION_ERROR
            self.startup_event.set()
        elif message['type'] == 'lifespan.cleanup.complete':
            assert self.startup_event.is_set(), STATE_TRANSITION_ERROR
            assert not self.cleanup_event.is_set(), STATE_TRANSITION_ERROR
            self.cleanup_event.set()
        else:
            error = 'Got invalid message type on lifespan protocol "%s"'
            raise RuntimeError(error % message['type'])

    async def receive(self):
        message = await self.receive_queue.get()
        return message

    async def wait_startup(self):
        await self.receive_queue.put({'type': 'lifespan.startup'})
        await asyncio.wait_for(self.startup_event.wait(), timeout=self.startup_timeout)

    async def wait_cleanup(self):
        await self.receive_queue.put({'type': 'lifespan.cleanup'})
        await asyncio.wait_for(self.cleanup_event.wait(), timeout=self.cleanup_timeout)
