from uvicorn.config import get_logger, Config, LOG_LEVELS, HTTP_PROTOCOLS, WS_PROTOCOLS, LOOP_SETUPS
from uvicorn.global_state import GlobalState
from uvicorn.lifespan import Lifespan
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


LEVEL_CHOICES = click.Choice(LOG_LEVELS.keys())
HTTP_CHOICES = click.Choice(HTTP_PROTOCOLS.keys())
WS_CHOICES = click.Choice(WS_PROTOCOLS.keys())
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
@click.option(
    "--disable-lifespan",
    is_flag=True,
    default=False,
    help="Disable lifespan events (such as startup and shutdown) within an ASGI application.",
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
    wsgi: bool,
    debug: bool,
    log_level: str,
    no_access_log: bool,
    proxy_headers: bool,
    root_path: str,
    limit_concurrency: int,
    limit_max_requests: int,
    timeout_keep_alive: int,
    disable_lifespan: bool,
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
        "log_level": log_level,
        "access_log": not no_access_log,
        "wsgi": wsgi,
        "debug": debug,
        "proxy_headers": proxy_headers,
        "root_path": root_path,
        "limit_concurrency": limit_concurrency,
        "limit_max_requests": limit_max_requests,
        "timeout_keep_alive": timeout_keep_alive,
        "disable_lifespan": disable_lifespan,
    }

    if debug:
        logger = get_logger(log_level)
        reloader = StatReload(logger)
        reloader.run(run, kwargs)
    else:
        run(**kwargs)


def run(app, **kwargs):
    if 'global_state' in kwargs:
        global_state = kwargs.pop('global_state')
    else:
        global_state = GlobalState()

    config = Config(app, **kwargs)

    server = Server(config=config, global_state=global_state)
    server.run()


class Server:
    def __init__(self, config, global_state):
        self.config = config
        self.global_state = global_state

        self.app = config.app
        self.loop = config.loop
        self.logger = config.logger
        self.limit_max_requests = config.limit_max_requests
        self.disable_lifespan = config.disable_lifespan
        self.on_tick = config.http_protocol_class.tick
        self.should_exit = False
        self.force_exit = False
        self.pid = os.getpid()

        def create_protocol():
            return config.http_protocol_class(
                config=config,
                global_state=global_state
            )

        self.create_protocol = create_protocol

    def set_signal_handlers(self):
        if not self.config.install_signal_handlers:
            return

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

    def run(self):
        self.logger.info("Started server process [{}]".format(self.pid))
        self.set_signal_handlers()
        if not self.disable_lifespan:
            self.lifespan = Lifespan(self.app, self.logger)
            if self.lifespan.is_enabled:
                self.logger.info("Waiting for application startup.")
                self.loop.create_task(self.lifespan.run())
                self.loop.run_until_complete(self.lifespan.wait_startup())
                if self.lifespan.error_occured:
                    self.logger.error("Application startup failed. Exiting.")
                    return
            else:
                self.logger.debug(
                    "Lifespan protocol is not recognized by the application"
                )
        self.loop.run_until_complete(self.create_server())
        self.loop.create_task(self.tick())
        self.global_state.started.set()
        self.loop.run_forever()

    async def create_server(self):
        config = self.config

        if config.sock is not None:
            # Use an existing socket.
            self.server = await self.loop.create_server(
                self.create_protocol, sock=config.sock
            )
            message = "Uvicorn running on socket %s (Press CTRL+C to quit)"
            self.logger.info(message % str(config.sock.getsockname()))

        elif config.uds is not None:
            # Create a socket using UNIX domain socket.
            self.server = await self.loop.create_unix_server(
                self.create_protocol, path=config.uds
            )
            message = "Uvicorn running on unix socket %s (Press CTRL+C to quit)"
            self.logger.info(message % config.uds)

        else:
            # Standard case. Create a socket from a host/port pair.
            self.server = await self.loop.create_server(
                self.create_protocol, host=config.host, port=config.port
            )
            message = "Uvicorn running on http://%s:%d (Press CTRL+C to quit)"
            self.logger.info(message % (config.host, config.port))

    async def tick(self):
        should_limit_requests = self.limit_max_requests is not None

        while not self.should_exit:
            if (
                should_limit_requests
                and self.global_state.total_requests >= self.limit_max_requests
            ):
                break
            self.on_tick()
            await asyncio.sleep(1)

        self.logger.info("Stopping server process [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        for connection in list(self.global_state.connections):
            connection.shutdown()

        await asyncio.sleep(0.1)
        if self.global_state.connections and not self.force_exit:
            self.logger.info("Waiting for connections to close. (Press CTRL+C to force quit)")
            while self.global_state.connections and not self.force_exit:
                await asyncio.sleep(0.1)
        if self.global_state.tasks and not self.force_exit:
            self.logger.info("Waiting for background tasks to complete. (Press CTRL+C to force quit)")
            while self.global_state.tasks and not self.force_exit:
                await asyncio.sleep(0.1)

        if not self.disable_lifespan and self.lifespan.is_enabled and not self.force_exit:
            self.logger.info("Waiting for application shutdown.")
            await self.lifespan.wait_shutdown()

        if self.force_exit:
            self.logger.info("Forced quit.")

        self.loop.stop()


if __name__ == "__main__":
    main()
