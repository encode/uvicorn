from uvicorn.importer import import_from_string, ImportFromStringError
import asyncio
import click
import signal
import os
import logging
import platform
import sys


LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
HTTP_PROTOCOLS = {
    "auto": "uvicorn.protocols.http.auto:AutoHTTPProtocol",
    "h11": "uvicorn.protocols.http.h11:H11Protocol",
    "httptools": "uvicorn.protocols.http.httptools:HttpToolsProtocol",
}
LOOP_SETUPS = {
    "auto": "uvicorn.loops.auto:auto_loop_setup",
    "asyncio": "uvicorn.loops.asyncio:asyncio_setup",
    "uvloop": "uvicorn.loops.uvloop:uvloop_setup",
}

LEVEL_CHOICES = click.Choice(LOG_LEVELS.keys())
HTTP_CHOICES = click.Choice(HTTP_PROTOCOLS.keys())
LOOP_CHOICES = click.Choice(LOOP_SETUPS.keys())


@click.command()
@click.argument("app")
@click.option("--host", type=str, default="127.0.0.1", help="Host")
@click.option("--port", type=int, default=8000, help="Port")
@click.option("--loop", type=LOOP_CHOICES, default="auto", help="Event loop")
@click.option("--http", type=HTTP_CHOICES, default="auto", help="HTTP Handler")
@click.option("--workers", type=int, default=1, help="Number of worker processes")
@click.option("--log-level", type=LEVEL_CHOICES, default="info", help="Log level")
def main(app, host: str, port: int, loop: str, http: str, workers: int, log_level: str):
    sys.path.insert(0, ".")
    try:
        app = import_from_string(app)
    except ImportFromStringError as exc:
        click.error("Error loading ASGI app. %s" % exc)

    if workers != 1:
        raise click.UsageError(
            "Not yet available. For multiple worker processes, use gunicorn. "
            'eg. "gunicorn -w 4 -k uvicorn.workers.UvicornWorker".'
        )

    run(app, host, port, http, loop, log_level)


def run(app, host="127.0.0.1", port=8000, loop="auto", http="auto", log_level="info"):
    log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    logger = logging.getLogger()

    app = import_from_string(app)
    loop_setup = import_from_string(LOOP_SETUPS[loop])
    protocol_class = import_from_string(HTTP_PROTOCOLS[http])

    loop = loop_setup()

    server = Server(app, host, port, loop, logger, protocol_class)
    server.run()


class Server:
    def __init__(
        self,
        app,
        host="127.0.0.1",
        port=8000,
        loop=None,
        logger=None,
        protocol_class=None,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.loop = loop or asyncio.get_event_loop()
        self.logger = logger or logging.getLogger()
        self.server = None
        self.should_exit = False
        self.pid = os.getpid()
        self.protocol_class = protocol_class

    def set_signal_handlers(self):
        handled = (
            signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
            signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
        )
        try:
            for sig in handled:
                self.loop.add_signal_handler(sig, self.handle_exit, sig, None)
        except NotImplementedError:
            # Windows
            for sig in handled:
                signal.signal(sig, self.handle_exit)

    def run(self):
        self.set_signal_handlers()
        self.loop.run_until_complete(self.create_server())
        if self.server is not None:
            message = "* Uvicorn running on http://%s:%d 🦄 (Press CTRL+C to quit)"
            click.echo(message % (self.host, self.port))
            self.logger.info("Started worker [{}]".format(self.pid))
            self.loop.create_task(self.tick())
            self.loop.run_forever()

    def handle_exit(self, sig, frame):
        if hasattr(sig, "name"):
            msg = "Received signal %s. Shutting down." % sig.name
        else:
            msg = "Received signal. Shutting down."
        self.logger.warning(msg)
        self.should_exit = True

    def create_protocol(self):
        try:
            return self.protocol_class(app=self.app, loop=self.loop, logger=self.logger)
        except Exception as exc:
            self.logger.error(exc)
            self.should_exit = True

    async def create_server(self):
        try:
            self.server = await self.loop.create_server(
                self.create_protocol, host=self.host, port=self.port
            )
        except Exception as exc:
            self.logger.error(exc)

    async def tick(self):
        while not self.should_exit:
            self.protocol_class.tick()
            await asyncio.sleep(1)

        self.logger.info("Stopping worker [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        self.loop.stop()


if __name__ == "__main__":
    main()
