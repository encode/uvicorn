from uvicorn.protocols.http import H11Protocol, HttpToolsProtocol

import asyncio
import click
import importlib
import signal
import os
import logging
import sys


LOOP_CHOICES = click.Choice(["uvloop", "asyncio"])
LEVEL_CHOICES = click.Choice(["debug", "info", "warning", "error", "critical"])
HTTP_CHOICES = click.Choice(["httptools", "h11"])
LOG_LEVELS = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
HTTP_PROTOCOLS = {"h11": H11Protocol, "httptools": HttpToolsProtocol}


@click.command()
@click.argument("app")
@click.option("--host", type=str, default="127.0.0.1", help="Host")
@click.option("--port", type=int, default=8000, help="Port")
@click.option("--loop", type=LOOP_CHOICES, default="uvloop", help="Event loop")
@click.option("--http", type=HTTP_CHOICES, default="httptools", help="HTTP Handler")
@click.option("--workers", type=int, default=1, help="Number of worker processes")
@click.option("--log-level", type=LEVEL_CHOICES, default="info", help="Log level")
def main(app, host: str, port: int, loop: str, http: str, workers: int, log_level: str):
    log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    logger = logging.getLogger()
    loop = get_event_loop(loop)

    sys.path.insert(0, ".")
    app = load_app(app)
    protocol_class = HTTP_PROTOCOLS[http]

    if workers != 1:
        raise click.UsageError(
            'Not yet available. For multiple worker processes, use gunicorn. '
            'eg. "gunicorn -w 4 -k uvicorn.workers.UvicornWorker".'
        )

    server = Server(app, host, port, loop, logger, protocol_class)
    server.run()


def run(app, host="127.0.0.1", port=8000, log_level="info"):
    log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)

    loop = get_event_loop("uvloop")
    logger = logging.getLogger()
    protocol_class = HttpToolsProtocol

    server = Server(app, host, port, loop, logger, protocol_class)
    server.run()


def load_app(app):
    if not isinstance(app, str):
        return app

    if ":" not in app:
        message = 'Invalid app string "{app}". Must be in format "<module>:<app>".'
        raise click.UsageError(message.format(app=app))

    module_str, attrs = app.split(":", 1)
    try:
        module = importlib.import_module(module_str)
    except ModuleNotFoundError:
        message = 'Error loading ASGI app. Could not import module "{module_str}".'
        raise click.UsageError(message.format(module_str=module_str))

    try:
        for attr in attrs.split('.'):
            asgi_app = getattr(module, attr)
    except AttributeError:
        message = 'Error loading ASGI app. No app "{attrs}" found in module "{module_str}".'
        raise click.UsageError(message.format(attrs=attrs, module_str=module_str))

    return asgi_app


def get_event_loop(loop):
    if loop == "uvloop":
        import uvloop

        asyncio.get_event_loop().close()
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    return asyncio.get_event_loop()


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
        handled = (signal.SIGQUIT, signal.SIGTERM, signal.SIGINT, signal.SIGABRT)
        for sig in handled:
            self.loop.add_signal_handler(sig, self.handle_exit, sig, None)

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
        self.logger.warning("Received signal {}. Shutting down.".format(sig.name))
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
