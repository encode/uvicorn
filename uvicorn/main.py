from uvicorn.debug import DebugMiddleware
from uvicorn.importer import import_from_string, ImportFromStringError
from uvicorn.reloaders.statreload import StatReload
import asyncio
import click
import signal
import os
import logging
import socket
import sys
import time
import multiprocessing


LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
HTTP_PROTOCOLS = {
    "auto": "uvicorn.protocols.http.auto:AutoHTTPProtocol",
    "h11": "uvicorn.protocols.http.h11_impl:H11Protocol",
    "httptools": "uvicorn.protocols.http.httptools_impl:HttpToolsProtocol",
}
LOOP_SETUPS = {
    "auto": "uvicorn.loops.auto:auto_loop_setup",
    "asyncio": "uvicorn.loops.asyncio:asyncio_setup",
    "uvloop": "uvicorn.loops.uvloop:uvloop_setup",
}

LEVEL_CHOICES = click.Choice(LOG_LEVELS.keys())
HTTP_CHOICES = click.Choice(HTTP_PROTOCOLS.keys())
LOOP_CHOICES = click.Choice(LOOP_SETUPS.keys())

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


def get_socket(host, port):
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    return sock


def get_logger(log_level):
    log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    return logging.getLogger()


@click.command()
@click.argument("app")
@click.option("--host", type=str, default="127.0.0.1", help="Host")
@click.option("--port", type=int, default=8000, help="Port")
@click.option("--loop", type=LOOP_CHOICES, default="auto", help="Event loop")
@click.option("--http", type=HTTP_CHOICES, default="auto", help="HTTP Handler")
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode")
@click.option("--log-level", type=LEVEL_CHOICES, default="info", help="Log level")
def main(app, host: str, port: int, loop: str, http: str, debug: bool, log_level: str):
    sys.path.insert(0, ".")

    kwargs = {
        "app": app,
        "host": host,
        "port": port,
        "loop": loop,
        "http": http,
        "log_level": log_level,
        "debug": debug,
    }

    if debug:
        logger = get_logger(log_level)
        reloader = StatReload(logger)
        reloader.run(run, kwargs)
    else:
        run(**kwargs)


def run(
    app,
    host="127.0.0.1",
    port=8000,
    loop="auto",
    http="auto",
    log_level="info",
    debug=False,
):
    try:
        app = import_from_string(app)
    except ImportFromStringError as exc:
        click.echo("Error loading ASGI app. %s" % exc)
        sys.exit(1)

    if debug:
        app = DebugMiddleware(app)

    logger = get_logger(log_level)
    loop_setup = import_from_string(LOOP_SETUPS[loop])
    protocol_class = import_from_string(HTTP_PROTOCOLS[http])

    loop = loop_setup()

    server = Server(
        app=app,
        host=host,
        port=port,
        logger=logger,
        loop=loop,
        protocol_class=protocol_class,
    )
    server.run()


class Server:
    def __init__(self, app, host, port, logger, loop, protocol_class):
        self.app = app
        self.host = host
        self.port = port
        self.logger = logger
        self.loop = loop
        self.protocol_class = protocol_class
        self.should_exit = False
        self.pid = os.getpid()

    def set_signal_handlers(self):
        try:
            for sig in HANDLED_SIGNALS:
                self.loop.add_signal_handler(sig, self.handle_exit, sig, None)
        except NotImplementedError:
            # Windows
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, self.handle_exit)

    def handle_exit(self, sig, frame):
        self.should_exit = True

    def run(self):
        self.logger.info("Started server process [{}]".format(self.pid))
        self.set_signal_handlers()
        self.loop.run_until_complete(self.create_server())
        self.loop.create_task(self.tick())
        self.loop.run_forever()

    def create_protocol(self):
        return self.protocol_class(app=self.app, loop=self.loop, logger=self.logger)

    async def create_server(self):
        self.server = await self.loop.create_server(
            self.create_protocol, self.host, self.port
        )
        message = "* Uvicorn running on http://%s:%d 🦄 (Press CTRL+C to quit)"
        click.echo(message % (self.host, self.port))

    async def tick(self):
        while not self.should_exit:
            self.protocol_class.tick()
            await asyncio.sleep(1)

        self.logger.info("Stopping server process [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        self.loop.stop()


if __name__ == "__main__":
    main()
