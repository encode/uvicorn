from gunicorn.util import import_app
from uvicorn.protocols import http
import argparse
import asyncio
import functools
import logging
import os
import signal
import uvloop


logger = logging.getLogger()


class UvicornServer():
    def __init__(self):
        self.servers = []
        self.alive = True

    def run(self, app, host, port):
        asyncio.get_event_loop().close()
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

        loop = asyncio.get_event_loop()

        loop.add_signal_handler(signal.SIGQUIT, self.handle_exit, signal.SIGQUIT, None)
        loop.add_signal_handler(signal.SIGTERM, self.handle_exit, signal.SIGTERM, None)
        loop.add_signal_handler(signal.SIGINT, self.handle_exit, signal.SIGINT, None)
        loop.add_signal_handler(signal.SIGABRT, self.handle_exit, signal.SIGABRT, None)

        loop.create_task(self.create_server(loop, app, host, port))
        loop.create_task(self.tick(loop))

        logger.warning('Starting worker [{}] serving at: {}:{}'.format(os.getpid(), host, port))

        loop.run_forever()

    async def create_server(self, loop, app, host, port):
        protocol = functools.partial(http.HttpProtocol, consumer=app, loop=loop)
        server = await loop.create_server(protocol, host=host, port=port)
        self.servers.append(server)

    async def tick(self, loop):

        while self.alive:
            http.set_time_and_date()
            await asyncio.sleep(1)

        logger.warning("Stopping worker [{}]".format(os.getpid()))

        for server in self.servers:
            server.close()
            await server.wait_closed()

        loop.stop()

    def handle_exit(self, sig, frame):
        self.alive = False
        logger.warning("Received signal {}. Shutting down.".format(sig.name))


def run(app, host="127.0.0.1", port=8000):
    UvicornServer().run(app, host=host, port=port)
