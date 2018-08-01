import trio
import asyncio
import functools
import os
import signal
import ssl
import sys

from gunicorn.workers.base import Worker
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

import trio
import trio_protocol


class UvicornWorker(Worker):
    """
    A worker class for Gunicorn that interfaces with an ASGI consumer callable,
    rather than a WSGI callable.

    It runs using trio.
    """

    protocol_class = H11Protocol

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.servers = []
        self.exit_code = 0
        self.log.level = self.log.loglevel        
        self.killed = trio.Event()
    
    def run(self):
        async def main():
            async with trio.open_nursery() as nursery:
                nursery.start_soon(self.tick)
                nursery.start_soon(self.handle_signals)
                await self.create_servers(nursery)

                await self.killed.wait()
                nursery.cancel_scope.cancel()

        trio.run(main)
        sys.exit(self.exit_code)

    async def handle_signals(self):
        # # Don't let SIGTERM and SIGUSR1 disturb active requests
        # # by interrupting system calls
        # signal.siginterrupt(signal.SIGTERM, False)
        # signal.siginterrupt(signal.SIGUSR1, False)

        signals = {
            signal.SIGQUIT: self.handle_quit,
            signal.SIGTERM: self.handle_exit,
            signal.SIGINT: self.handle_quit,
            signal.SIGWINCH: self.handle_winch,
            signal.SIGUSR1: self.handle_usr1,
            signal.SIGABRT: self.handle_abort,
        }
        with trio.catch_signals(signals) as batched_signal_aiter:
            async for batch in batched_signal_aiter:
                for signum in batch:
                    signals[signum](signum, None)

    def init_signals(self):        
        pass

    async def create_servers(self, nursery):
        cfg = self.cfg
        app = self.wsgi

        ssl_ctx = self.create_ssl_context(self.cfg) if self.cfg.is_ssl else None

        for sock in self.sockets:
            state = {"total_requests": 0}
            protocol = functools.partial(
                self.protocol_class, app=app, state=state, logger=self.log,
                loop=trio_protocol.Loop(nursery)
            )
            server = await trio_protocol.create_server(
                nursery, protocol, sock=sock, ssl=ssl_ctx
            )
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

    def handle_quit(self, sig, frame):
        self.alive = False
        self.killed.set()
        self.cfg.worker_int(self)

    def handle_abort(self, sig, frame):
        self.alive = False
        self.killed.set()
        self.exit_code = 1
        self.cfg.worker_abort(self)

    async def tick(self):
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
                await trio.sleep(1)

        for server, state in self.servers:
            server.close()
            await server.wait_closed()
        loop.stop()


class UvicornH11Worker(UvicornWorker):

    protocol_class = H11Protocol
