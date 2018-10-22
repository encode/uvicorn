import asyncio
import functools
import logging
import os
import signal
import ssl
import sys

import uvloop

from gunicorn.workers.base import Worker
from uvicorn.lifespan import Lifespan
from uvicorn.middleware.message_logger import MessageLoggerMiddleware
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol


class UvicornWorker(Worker):
    """
    A worker class for Gunicorn that interfaces with an ASGI consumer callable,
    rather than a WSGI callable.

    We use a couple of packages from MagicStack in order to achieve an
    extremely high-throughput and low-latency implementation:

    * `uvloop` as the event loop policy.
    * `httptools` as the HTTP request parser.
    """

    protocol_class = HttpToolsProtocol
    ws_protocol_class = WebSocketProtocol
    loop = "uvloop"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servers = []
        self.exit_code = 0
        self.log.level = self.log.loglevel

    def init_process(self):
        if self.loop == "uvloop":
            # Close any existing event loop before setting a
            # new policy.
            asyncio.get_event_loop().close()

            # Setup uvloop policy, so that every
            # asyncio.get_event_loop() will create an instance
            # of uvloop event loop.
            asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

        super().init_process()

    def run(self):
        app = self.wsgi

        if self.log.level <= logging.DEBUG:
            app = MessageLoggerMiddleware(app)

        loop = asyncio.get_event_loop()

        self.lifespan = Lifespan(app, self.log)
        if self.lifespan.is_enabled:
            loop.create_task(self.lifespan.run())
            loop.run_until_complete(self.lifespan.wait_startup())
        else:
            self.log.debug("Lifespan protocol is not recognized by the application")

        loop.create_task(self.create_servers(loop, app))
        loop.create_task(self.tick(loop))
        loop.run_forever()
        sys.exit(self.exit_code)

    def init_signals(self):
        # Set up signals through the event loop API.
        loop = asyncio.get_event_loop()

        loop.add_signal_handler(signal.SIGQUIT, self.handle_quit, signal.SIGQUIT, None)

        loop.add_signal_handler(signal.SIGTERM, self.handle_exit, signal.SIGTERM, None)

        loop.add_signal_handler(signal.SIGINT, self.handle_quit, signal.SIGINT, None)

        loop.add_signal_handler(
            signal.SIGWINCH, self.handle_winch, signal.SIGWINCH, None
        )

        loop.add_signal_handler(signal.SIGUSR1, self.handle_usr1, signal.SIGUSR1, None)

        loop.add_signal_handler(signal.SIGABRT, self.handle_abort, signal.SIGABRT, None)

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

    async def create_servers(self, loop, app):
        cfg = self.cfg

        ssl_ctx = self.create_ssl_context(self.cfg) if self.cfg.is_ssl else None

        for sock in self.sockets:
            state = {"total_requests": 0}
            connections = set()
            protocol = functools.partial(
                self.protocol_class,
                app=app,
                loop=loop,
                connections=connections,
                state=state,
                logger=self.log,
                ws_protocol_class=WebSocketProtocol,
                timeout_keep_alive=self.cfg.keepalive
            )
            server = await loop.create_server(protocol, sock=sock, ssl=ssl_ctx)
            self.servers.append((server, state))

    def create_ssl_context(self, cfg):
        ctx = ssl.SSLContext(cfg.ssl_version)
        ctx.load_cert_chain(cfg.certfile, cfg.keyfile)
        ctx.verify_mode = cfg.cert_reqs
        if cfg.ca_certs:
            ctx.load_verify_locations(cfg.ca_certs)
        if cfg.ciphers:
            ctx.set_ciphers(cfg.ciphers)
        return ctx

    async def tick(self, loop):
        pid = os.getpid()
        cycle = 0

        while self.alive:
            self.protocol_class.tick()

            cycle = (cycle + 1) % 10
            if cycle == 0:
                self.notify()

            req_count = sum([state["total_requests"] for server, state in self.servers])
            if self.max_requests and req_count > self.max_requests:
                self.alive = False
                self.log.info("Max requests exceeded, shutting down: %s", self)
            elif self.ppid != os.getppid():
                self.alive = False
                self.log.info("Parent changed, shutting down: %s", self)
            else:
                await asyncio.sleep(1)

        for server, state in self.servers:
            server.close()
            await server.wait_closed()

        if self.lifespan.is_enabled:
            await self.lifespan.wait_shutdown()

        loop.stop()


class UvicornH11Worker(UvicornWorker):
    protocol_class = H11Protocol
    loop = "asyncio"
