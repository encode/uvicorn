from uvicorn.protocols.http import H11Protocol, HttpToolsProtocol

import asyncio
import click
import importlib
import signal
import os
import logging
import sys


logger = logging.getLogger()


class ConfigurationError(Exception):
    pass


class Server:
    def __init__(self, app, host='127.0.0.1', port=5000, loop=None, protocol_class=None):
        self.app = app
        self.host = host
        self.port = port
        self.loop = loop or asyncio.get_event_loop()
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
            message = "Uvicorn running on http://%s:%d 🦄 (Press CTRL+C to quit)"
            logger.info(message, self.host, self.port)
            logger.info("Started worker [{}]".format(self.pid))
            self.loop.create_task(self.tick())
            self.loop.run_forever()

    def handle_exit(self, sig, frame):
        logger.warning("Received signal {}. Shutting down.".format(sig.name))
        self.should_exit = True

    def create_protocol(self):
        try:
            return self.protocol_class(app=self.app, loop=self.loop)
        except Exception as exc:
            logger.error(exc)
            self.should_exit = True

    async def create_server(self):
        try:
            self.server = await self.loop.create_server(
                self.create_protocol, host=self.host, port=self.port
            )
        except PermissionError as exc:
            logger.error(exc)

    async def tick(self):
        while not self.should_exit:
            # http.set_time_and_date()
            await asyncio.sleep(1)

        logger.info("Stopping worker [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        self.loop.stop()


LOOP_CHOICES = click.Choice(["uvloop", "asyncio"])
LEVEL_CHOICES = click.Choice(["debug", "info", "warn", "error"])
HTTP_CHOICES = click.Choice(["h11", "httptools"])
LOG_LEVELS = {
    "error": logging.ERROR,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}
HTTP_PROTOCOLS = {
    "h11": H11Protocol,
    "httptools": HttpToolsProtocol,
}


def load_app(app):
    if not isinstance(app, str):
        return app

    if ':' not in app:
        message = 'Invalid app string "{app}". Must be in format "<module>:<app>".'
        raise click.UsageError(message.format(app=app))

    module_str, _, attr = app.partition(":")
    try:
        module = importlib.import_module(module_str)
    except ModuleNotFoundError:
        message = 'Error loading ASGI app. Could not import module "{module_str}".'
        raise click.UsageError(message.format(module_str=module_str))

    try:
        return getattr(module, attr)
    except AttributeError:
        message = 'Error loading ASGI app. No attribute "{attr}" found in module "{module_str}".'
        raise click.UsageError(message.format(attr=attr, module_str=module_str))


def get_event_loop(loop):
    if loop != "uvloop":
        import uvloop
        asyncio.get_event_loop().close()
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    return asyncio.get_event_loop()


@click.command()
@click.argument("app")
@click.option("--host", type=str, default="127.0.0.1", help="Host")
@click.option("--port", type=int, default=5000, help="Port")
@click.option("--loop", type=LOOP_CHOICES, default="asyncio", help="Event loop")
@click.option("--http", type=HTTP_CHOICES, default="httptools", help="HTTP Handler")
@click.option("--log-level", type=LEVEL_CHOICES, default="info", help="Log level")
def main(app, host: str, port: int, loop: str, http: str, log_level: str):
    log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)

    app = load_app(app)
    loop = get_event_loop(loop)
    protocol_class = HTTP_PROTOCOLS[http]
    server = Server(app, host, port, loop, protocol_class)
    server.run()


if __name__ == "__main__":
    main()
