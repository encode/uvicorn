from uvicorn.debug import DebugMiddleware
from uvicorn.importer import import_from_string, ImportFromStringError
from uvicorn.reloaders.noreload import NoReload
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
    sock.set_inheritable(True)
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
@click.option("--workers", type=int, default=1, help="Number of worker processes")
@click.option(
    "--debug", type=bool, is_flag=True, default=False, help="Enable debug mode"
)
@click.option("--log-level", type=LEVEL_CHOICES, default="info", help="Log level")
def main(
    app,
    host: str,
    port: int,
    loop: str,
    http: str,
    workers: int,
    debug: bool,
    log_level: str,
):
    sys.path.insert(0, ".")

    kwargs = {
        "app": app,
        "host": host,
        "port": port,
        "loop": loop,
        "http": http,
        "log_level": log_level,
        "workers": workers,
        "debug": debug,
    }
    run(**kwargs)


def run(
    app,
    host="127.0.0.1",
    port=8000,
    loop="auto",
    http="auto",
    log_level="info",
    workers=1,
    debug=False,
):
    sock = get_socket(host, port)
    logger = get_logger(log_level)
    pid = os.getpid()

    message = "* Uvicorn running on http://%s:%d 🦄 (Press CTRL+C to quit)"
    click.echo(message % (host, port))
    logger.info("Started parent [{}]".format(pid))

    processes = []
    seen_shutdown = False
    seen_restart = False

    if debug:
        reloader = StatReload(logger)
    else:
        reloader = NoReload()

    def shutdown(sig, frame):
        nonlocal seen_shutdown

        seen_shutdown = True

        logger.warning("Got signal %s. Shutting down.", signal.Signals(sig).name)

        for process, event in processes:
            event.set()

    for sig in HANDLED_SIGNALS:
        signal.signal(sig, shutdown)

    while not seen_shutdown:
        for _ in range(workers):
            event = multiprocessing.Event()
            kwargs = {
                "app": app,
                "sock": sock,
                "event": event,
                "logger": logger,
                "loop": loop,
                "http": http,
                "debug": debug,
            }
            process = multiprocessing.Process(target=run_one, kwargs=kwargs)
            process.start()
            processes.append((process, event))

        while not (seen_shutdown or seen_restart):
            if not any([process.is_alive() for process, event in processes]):
                seen_shutdown = True
            time.sleep(0.2)
            seen_restart = reloader.should_restart()

        if seen_restart:
            for process, event in processes:
                event.set()
            seen_restart = False
            reloader.clear()

        for process, event in processes:
            process.join()

    logger.info("Stopping parent [{}]".format(pid))


def run_one(app, sock, event, logger, debug=False, loop="auto", http="auto"):
    try:
        app = import_from_string(app)
    except ImportFromStringError as exc:
        click.echo("Error loading ASGI app. %s" % exc)
        sys.exit(1)

    if debug:
        app = DebugMiddleware(app)

    loop_setup = import_from_string(LOOP_SETUPS[loop])
    protocol_class = import_from_string(HTTP_PROTOCOLS[http])

    loop = loop_setup()

    # Ignore signals, instead allowing the parent process to handle them.
    # Communication with subprocesses is via the 'multiprocessing.Event' instance.
    def ignore(sig, frame):
        pass

    for sig in HANDLED_SIGNALS:
        signal.signal(sig, ignore)

    server = Server(app, sock, event, logger, loop, protocol_class)
    server.run()


class Server:
    def __init__(self, app, sock, event, logger, loop, protocol_class):
        self.app = app
        self.sock = sock
        self.event = event
        self.logger = logger
        self.loop = loop
        self.protocol_class = protocol_class
        self.pid = os.getpid()

    def run(self):
        self.logger.info("Started worker [{}]".format(self.pid))
        self.loop.run_until_complete(self.create_server())
        self.loop.create_task(self.tick())
        self.loop.run_forever()

    def create_protocol(self):
        try:
            return self.protocol_class(app=self.app, loop=self.loop, logger=self.logger)
        except Exception as exc:
            self.logger.error(exc)
            self.event.set()

    async def create_server(self):
        try:
            self.server = await self.loop.create_server(
                self.create_protocol, sock=self.sock
            )
        except Exception as exc:
            self.logger.error(exc)
            self.event.set()

    async def tick(self):
        while not self.event.is_set():
            self.protocol_class.tick()
            await asyncio.sleep(1)

        self.logger.info("Stopping worker [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        self.loop.stop()


if __name__ == "__main__":
    main()
