import asyncio
import functools
import os
import signal
import socket
import sys
import time
from email.utils import formatdate

import click

from uvicorn.config import (
    HTTP_PROTOCOLS,
    LIFESPAN,
    LOG_LEVELS,
    LOOP_SETUPS,
    WS_PROTOCOLS,
    Config,
    get_logger,
)
from uvicorn.reloaders.statreload import StatReload

LEVEL_CHOICES = click.Choice(LOG_LEVELS.keys())
HTTP_CHOICES = click.Choice(HTTP_PROTOCOLS.keys())
WS_CHOICES = click.Choice(WS_PROTOCOLS.keys())
LIFESPAN_CHOICES = click.Choice(LIFESPAN.keys())
LOOP_CHOICES = click.Choice(LOOP_SETUPS.keys())

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


@click.command()
@click.argument("app")
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="Bind socket to this host.",
    show_default=True,
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Bind socket to this port.",
    show_default=True,
)
@click.option("--uds", type=str, default=None, help="Bind to a UNIX domain socket.")
@click.option(
    "--fd", type=int, default=None, help="Bind to socket from this file descriptor."
)
@click.option(
    "--loop",
    type=LOOP_CHOICES,
    default="auto",
    help="Event loop implementation.",
    show_default=True,
)
@click.option(
    "--http",
    type=HTTP_CHOICES,
    default="auto",
    help="HTTP protocol implementation.",
    show_default=True,
)
@click.option(
    "--ws",
    type=WS_CHOICES,
    default="auto",
    help="WebSocket protocol implementation.",
    show_default=True,
)
@click.option(
    "--lifespan",
    type=LIFESPAN_CHOICES,
    default="auto",
    help="Lifespan implementation.",
    show_default=True,
)
@click.option(
    "--wsgi",
    is_flag=True,
    default=False,
    help="Use WSGI as the application interface, instead of ASGI.",
)
@click.option("--debug", is_flag=True, default=False, help="Enable debug mode.")
@click.option(
    "--log-level",
    type=LEVEL_CHOICES,
    default="info",
    help="Log level.",
    show_default=True,
)
@click.option(
    "--no-access-log", is_flag=True, default=False, help="Disable access log."
)
@click.option(
    "--proxy-headers",
    is_flag=True,
    default=False,
    help="Use X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to populate remote address info.",
)
@click.option(
    "--root-path",
    type=str,
    default="",
    help="Set the ASGI 'root_path' for applications submounted below a given URL path.",
)
@click.option(
    "--limit-concurrency",
    type=int,
    default=None,
    help="Maximum number of concurrent connections or tasks to allow, before issuing HTTP 503 responses.",
)
@click.option(
    "--limit-max-requests",
    type=int,
    default=None,
    help="Maximum number of requests to service before terminating the process.",
)
@click.option(
    "--timeout-keep-alive",
    type=int,
    default=5,
    help="Close Keep-Alive connections if no new data is received within this timeout.",
    show_default=True,
)
def main(
    app,
    host: str,
    port: int,
    uds: str,
    fd: int,
    loop: str,
    http: str,
    ws: str,
    lifespan: str,
    wsgi: bool,
    debug: bool,
    log_level: str,
    no_access_log: bool,
    proxy_headers: bool,
    root_path: str,
    limit_concurrency: int,
    limit_max_requests: int,
    timeout_keep_alive: int,
):
    sys.path.insert(0, ".")

    kwargs = {
        "app": app,
        "host": host,
        "port": port,
        "uds": uds,
        "fd": fd,
        "loop": loop,
        "http": http,
        "ws": ws,
        "lifespan": lifespan,
        "log_level": log_level,
        "access_log": not no_access_log,
        "wsgi": wsgi,
        "debug": debug,
        "proxy_headers": proxy_headers,
        "root_path": root_path,
        "limit_concurrency": limit_concurrency,
        "limit_max_requests": limit_max_requests,
        "timeout_keep_alive": timeout_keep_alive,
    }

    if debug:
        logger = get_logger(log_level)
        reloader = StatReload(logger)
        reloader.run(run, kwargs)
    else:
        run(**kwargs)


def run(app, **kwargs):
    config = Config(app, **kwargs)
    server = Server(config=config)
    server.run()


class ServerState:
    """
    Shared servers state that is available between all protocol instances.
    """

    def __init__(self):
        self.total_requests = 0
        self.connections = set()
        self.tasks = set()
        self.default_headers = []


class Server:
    def __init__(self, config):
        self.config = config
        self.server_state = ServerState()

        self.started = False
        self.should_exit = False
        self.force_exit = False

    def run(self):
        process_id = os.getpid()

        config = self.config
        if not config.loaded:
            config.load()

        self.loop = config.loop_instance
        self.logger = config.logger_instance
        self.lifespan = config.lifespan_class(config)

        self.install_signal_handlers()

        self.logger.info("Started server process [{}]".format(process_id))
        self.loop.run_until_complete(self.startup())
        self.loop.run_until_complete(self.main_loop())
        self.loop.run_until_complete(self.shutdown())
        self.loop.stop()
        self.logger.info("Finished server process [{}]".format(process_id))

    async def startup(self):
        config = self.config

        await self.lifespan.startup()

        create_protocol = functools.partial(
            config.http_protocol_class, config=config, server_state=self.server_state
        )

        if config.sockets is not None:
            # Explicitly passed a list of open sockets.
            # We use this when the server is run from a Gunicorn worker.
            self.servers = []
            for socket in config.sockets:
                server = await self.loop.create_server(create_protocol, sock=socket)
                self.servers.append(server)

        elif config.fd is not None:
            # Use an existing socket, from a file descriptor.
            sock = socket.fromfd(config.fd, socket.AF_UNIX, socket.SOCK_STREAM)
            server = await self.loop.create_server(create_protocol, sock=sock)
            message = "Uvicorn running on socket %s (Press CTRL+C to quit)"
            self.logger.info(message % str(sock.getsockname()))
            self.servers = [server]

        elif config.uds is not None:
            # Create a socket using UNIX domain socket.
            server = await self.loop.create_unix_server(
                create_protocol, path=config.uds
            )
            message = "Uvicorn running on unix socket %s (Press CTRL+C to quit)"
            self.logger.info(message % config.uds)
            self.servers = [server]

        else:
            # Standard case. Create a socket from a host/port pair.
            server = await self.loop.create_server(
                create_protocol, host=config.host, port=config.port
            )
            message = "Uvicorn running on http://%s:%d (Press CTRL+C to quit)"
            self.logger.info(message % (config.host, config.port))
            self.servers = [server]

        self.started = True

    async def main_loop(self):
        counter = 0
        should_exit = await self.on_tick(counter)
        while not should_exit:
            counter += 1
            counter = counter % 864000
            await asyncio.sleep(0.1)
            should_exit = await self.on_tick(counter)

    async def on_tick(self, counter) -> bool:
        # Update the default headers, once per second.
        if counter % 10 == 0:
            current_time = time.time()
            current_date = formatdate(current_time, usegmt=True).encode()
            self.server_state.default_headers = [
                (b"server", b"uvicorn"),
                (b"date", current_date),
            ]

        # Callback to `callback_notify` once every `timeout_notify` seconds.
        if self.config.callback_notify is not None:
            if counter % (10 * self.config.timeout_notify) == 0:
                await self.config.callback_notify()

        # Determine if we should exit.
        if self.should_exit:
            return True
        if self.config.limit_max_requests is not None:
            return self.server_state.total_requests >= self.config.limit_max_requests
        return False

    async def shutdown(self):
        self.logger.info("Shutting down")

        # Stop accepting new connections.
        if not self.config.sockets:
            for server in self.servers:
                server.close()
            for server in self.servers:
                await server.wait_closed()

        # Request shutdown on all existing connections.
        for connection in list(self.server_state.connections):
            connection.shutdown()
        await asyncio.sleep(0.1)

        # Wait for existing connections to finish sending responses.
        if self.server_state.connections and not self.force_exit:
            msg = "Waiting for connections to close. (CTRL+C to force quit)"
            self.logger.info(msg)
            while self.server_state.connections and not self.force_exit:
                await asyncio.sleep(0.1)

        # Wait for existing tasks to complete.
        if self.server_state.tasks and not self.force_exit:
            msg = "Waiting for background tasks to complete. (CTRL+C to force quit)"
            self.logger.info(msg)
            while self.server_state.tasks and not self.force_exit:
                await asyncio.sleep(0.1)

        # Send the lifespan shutdown event, and wait for application shutdown.
        if not self.force_exit:
            await self.lifespan.shutdown()

    def install_signal_handlers(self):
        try:
            for sig in HANDLED_SIGNALS:
                self.loop.add_signal_handler(sig, self.handle_exit, sig, None)
        except NotImplementedError as exc:
            # Windows
            for sig in HANDLED_SIGNALS:
                signal.signal(sig, self.handle_exit)

    def handle_exit(self, sig, frame):
        if self.should_exit:
            self.force_exit = True
        else:
            self.should_exit = True


if __name__ == "__main__":
    main()
