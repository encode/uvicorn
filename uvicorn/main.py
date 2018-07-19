from uvicorn.importer import import_from_string, ImportFromStringError
import asyncio
import click
import signal
import os
import logging
import socket
import sys
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

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


def get_socket(host, port, reuse=False):
    sock = socket.socket()
    if reuse:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
        sock.set_inheritable(True)
    else:
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
@click.option("--workers", type=int, default=0, help="Number of worker processes")
@click.option("--log-level", type=LEVEL_CHOICES, default="info", help="Log level")
def main(app, host: str, port: int, loop: str, http: str, workers: int, log_level: str):
    sys.path.insert(0, ".")
    try:
        import_from_string(app)
    except ImportFromStringError as exc:
        click.error("Error loading ASGI app. %s" % exc)

    run(app, host, port, loop, http, log_level, workers)


def run(app, host="127.0.0.1", port=8000, loop="auto", http="auto", log_level="info", workers=0):
    sock = get_socket(host, port, reuse=bool(workers))
    logger = get_logger(log_level)

    message = "* Uvicorn running on http://%s:%d 🦄 (Press CTRL+C to quit)"
    click.echo(message % (host, port))

    if not workers:
        run_one(app, sock, loop, http, logger, event=None)
    else:
        run_multiple(app, sock, loop, http, logger, workers)


def run_multiple(app, sock, loop, http, logger, workers):
    """
    Run multiple workers, with a parent process handling signals.
    """
    pid = os.getpid()
    logger.info("Started parent [{}]".format(pid))

    processes = []

    def shutdown(sig, frame):
        logger.info('Got signal %s. Shutting down.', signal.Signals(sig).name)

        for process, event in processes:
            event.set()

    for sig in HANDLED_SIGNALS:
        signal.signal(sig, shutdown)

    for _ in range(workers):
        event = multiprocessing.Event()
        kwargs = {
            'app': app,
            'sock': sock,
            'loop': loop,
            'http': http,
            'logger': logger,
            'event': event,
        }
        process = multiprocessing.Process(target=run_one, kwargs=kwargs)
        process.start()
        processes.append((process, event))

    for process, event in processes:
        process.join()

    logger.info("Stopping parent [{}]".format(pid))


def run_one(app, sock, loop, http, logger, event=None):
    """
    Run a single process. If 'event' is passed then we're in parent/child
    mode and termination is handled via the event. Otherwise we're running
    in single-process mode.
    """
    app = import_from_string(app)
    loop_setup = import_from_string(LOOP_SETUPS[loop])
    protocol_class = import_from_string(HTTP_PROTOCOLS[http])

    loop = loop_setup()

    server = Server(app, sock, logger, loop, protocol_class, event=event)
    server.run()


class Server:
    def __init__(
        self,
        app,
        sock,
        logger,
        loop,
        protocol_class,
        event=None,
    ):
        self.app = app
        self.sock = sock
        self.logger = logger
        self.loop = loop
        self.protocol_class = protocol_class
        self.pid = os.getpid()
        if event is None:
            self.event = asyncio.Event()
            self.process_type = "process"
            self.setup_signals()
        else:
            self.event = event
            self.process_type = "worker"
            self.ignore_signals()

    def setup_signals(self):
        """
        If we're running in single process mode we need to handle signals
        on the event loop, and shutdown in response.
        """
        def shutdown(sig, frame):
            self.logger.info('Got signal %s. Shutting down.', signal.Signals(sig).name)
            self.event.set()

        try:
            for sig in HANDLED_SIGNALS:
                self.loop.add_signal_handler(sig, shutdown, sig, None)
        except NotImplementedError:
            # Windows
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, shutdown)

    def ignore_signals(self):
        """
        If we're running in parent/worker mode we need to ignore signals
        on the event loop.
        """
        def ignore(sig, frame):
            pass

        try:
            for sig in HANDLED_SIGNALS:
                self.loop.add_signal_handler(sig, ignore, sig, None)
        except NotImplementedError:
            # Windows
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, ignore)

    def run(self):
        self.logger.info("Started %s [%s]" % (self.process_type, self.pid))
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
            self.server = await self.loop.create_server(self.create_protocol, sock=self.sock)
        except Exception as exc:
            self.logger.error(exc)
            self.event.set()

    async def tick(self):
        while not self.event.is_set():
            self.protocol_class.tick()
            await asyncio.sleep(1)

        self.logger.info("Stopping %s [%s]" % (self.process_type, self.pid))
        self.server.close()
        await self.server.wait_closed()
        self.loop.stop()


if __name__ == "__main__":
    main()
