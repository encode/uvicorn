import asyncio
import functools
import signal
import sys

import uvloop

from gunicorn.workers.base import Worker
from uvicorn.protocols import http


class UvicornWorker(Worker):
    """
    A worker class for Gunicorn that interfaces with an ASGI consumer callable,
    rather than a WSGI callable.

    We use a couple of packages from MagicStack in order to achieve an
    extremely high-throughput and low-latency implementation:

    * `uvloop` as the event loop policy.
    * `httptools` as the HTTP request parser.
    """

    def __init__(self, *args, **kwargs):  # pragma: no cover
        super().__init__(*args, **kwargs)
        self.servers = []
        self.exit_code = 0

    def init_process(self):
        # Close any existing event loop before setting a
        # new policy.
        asyncio.get_event_loop().close()

        # Setup uvloop policy, so that every
        # asyncio.get_event_loop() will create an instance
        # of uvloop event loop.
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

        super().init_process()

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.create_servers(loop))
        loop.create_task(self.tick(loop))
        loop.run_forever()
        sys.exit(self.exit_code)

    def init_signals(self):
        # Set up signals through the event loop API.
        loop = asyncio.get_event_loop()

        loop.add_signal_handler(signal.SIGQUIT, self.handle_quit,
                                signal.SIGQUIT, None)

        loop.add_signal_handler(signal.SIGTERM, self.handle_exit,
                                signal.SIGTERM, None)

        loop.add_signal_handler(signal.SIGINT, self.handle_quit,
                                signal.SIGINT, None)

        loop.add_signal_handler(signal.SIGWINCH, self.handle_winch,
                                signal.SIGWINCH, None)

        loop.add_signal_handler(signal.SIGUSR1, self.handle_usr1,
                                signal.SIGUSR1, None)

        loop.add_signal_handler(signal.SIGABRT, self.handle_abort,
                                signal.SIGABRT, None)

        # Don't let SIGTERM and SIGUSR1 disturb active requests
        # by interrupting system calls
        signal.siginterrupt(signal.SIGTERM, False)
        signal.siginterrupt(signal.SIGUSR1, False)

    def handle_quit(self, sig, frame):
        self.alive = False
        self.cfg.worker_int(self)

    def handle_abort(self, sig, frame):
        self.alive = False
        self.exit_code = 1
        self.cfg.worker_abort(self)

    async def create_servers(self, loop):
        cfg = self.cfg
        consumer = self.wsgi

        for sock in self.sockets:
            protocol = functools.partial(
                http.HttpProtocol,
                consumer=consumer, loop=loop, sock=sock, cfg=cfg
            )
            server = await loop.create_server(protocol, sock=sock)
            self.servers.append(server)

    async def tick(self, loop):
        cycle = 0
        while self.alive:
            http.set_time_and_date()
            cycle = (cycle + 1) % 10
            if cycle == 0:
                self.notify()
            await asyncio.sleep(1)

        for server in self.servers:
            server.close()
            await server.wait_closed()
        loop.stop()
