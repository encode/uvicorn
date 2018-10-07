from uvicorn.importer import import_from_string, ImportFromStringError
from uvicorn.middleware.debug import DebugMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from uvicorn.middleware.message_logger import MessageLoggerMiddleware
from uvicorn.middleware.wsgi import WSGIMiddleware
from uvicorn.reloaders.statreload import StatReload
import asyncio
import click
import signal
import ssl
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
    "h2": "uvicorn.protocols.http.h2_impl:H2Protocol",
    "httptools": "uvicorn.protocols.http.httptools_impl:HttpToolsProtocol",
}
WS_PROTOCOLS = {
    "none": None,
    "auto": "uvicorn.protocols.websockets.auto:AutoWebSocketsProtocol",
    "websockets": "uvicorn.protocols.websockets.websockets_impl:WebSocketProtocol",
    "wsproto": "uvicorn.protocols.websockets.wsproto_impl:WSProtocol",
}
LOOP_SETUPS = {
    "auto": "uvicorn.loops.auto:auto_loop_setup",
    "asyncio": "uvicorn.loops.asyncio:asyncio_setup",
    "uvloop": "uvicorn.loops.uvloop:uvloop_setup",
}

LEVEL_CHOICES = click.Choice(LOG_LEVELS.keys())
HTTP_CHOICES = click.Choice(HTTP_PROTOCOLS.keys())
WS_CHOICES = click.Choice(WS_PROTOCOLS.keys())
LOOP_CHOICES = click.Choice(LOOP_SETUPS.keys())

HANDLED_SIGNALS = (
    signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
    signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
)


def get_logger(log_level):
    log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    return logging.getLogger("uvicorn")


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
    "--keyfile", type=str, default=None, help="SSL key file", show_default=True
)
@click.option(
    "--certfile", type=str, default=None, help="SSL certificate file", show_default=True
)
@click.option(
    "--ssl-version",
    type=int,
    default=ssl.PROTOCOL_TLS,
    help="SSL version to use (see stdlib ssl module's)",
    show_default=True,
)
@click.option(
    "--cert-reqs",
    type=int,
    default=ssl.CERT_NONE,
    help="Whether client certificate is required (see stdlib ssl module's)",
    show_default=True,
)
@click.option(
    "--ca-certs", type=str, default=None, help="CA certificates file", show_default=True
)
@click.option(
    "--ciphers",
    type=str,
    default="TLSv1.2",
    help="Ciphers to use (see stdlib ssl module's)",
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
    wsgi: bool,
    debug: bool,
    log_level: str,
    no_access_log: bool,
    proxy_headers: bool,
    root_path: str,
    limit_concurrency: int,
    limit_max_requests: int,
    timeout_keep_alive: int,
    keyfile: str,
    certfile: str,
    ssl_version: int,
    cert_reqs: int,
    ca_certs: str,
    ciphers: str,
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
        "keyfile": keyfile,
        "certfile": certfile,
        "ssl_version": ssl_version,
        "cert_reqs": cert_reqs,
        "ca_certs": ca_certs,
        "ciphers": ciphers,
    }

    if debug:
        logger = get_logger(log_level)
        reloader = StatReload(logger)
        reloader.run(run, kwargs)
    else:
        run(**kwargs)


def create_ssl_context(
    certfile, keyfile, ssl_version, cert_reqs, ca_certs, ciphers, enable_h2
):
    ctx = ssl.SSLContext(ssl_version)
    ctx.load_cert_chain(certfile, keyfile)
    ctx.verify_mode = cert_reqs
    if ca_certs:
        ctx.load_verify_locations(ca_certs)
    if ciphers:
        ctx.set_ciphers(ciphers)
    if enable_h2:
        ctx.options |= (
            ssl.OP_NO_SSLv2
            | ssl.OP_NO_SSLv3
            | ssl.OP_NO_TLSv1
            | ssl.OP_NO_TLSv1_1
            | ssl.OP_NO_COMPRESSION
            | ssl.OP_CIPHER_SERVER_PREFERENCE
        )
        for cipher in ctx.get_ciphers():
            if cipher["protocol"] in ["TLSv1.2", "TLSv1.3"]:
                break
        else:
            raise RuntimeError("HTTP/2 required tls version must higher than TLSv1.1")
        ctx.set_alpn_protocols(["h2", "http/1.1"])
        try:
            ctx.set_npn_protocols(["h2", "http/1.1"])
        except NotImplementedError:
            pass
    return ctx


def run(
    app,
    host="127.0.0.1",
    port=8000,
    uds=None,
    fd=None,
    loop="auto",
    http="auto",
    ws="auto",
    log_level="info",
    access_log=True,
    wsgi=False,
    debug=False,
    proxy_headers=False,
    root_path="",
    limit_concurrency=None,
    limit_max_requests=None,
    timeout_keep_alive=5,
    install_signal_handlers=True,
    ready_event=None,
    keyfile=None,
    certfile=None,
    ssl_version=None,
    cert_reqs=False,
    ca_certs=None,
    ciphers=None,
):

    if fd is None:
        sock = None
    else:
        host = None
        port = None
        sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)

    logger = get_logger(log_level)
    http_protocol_class = import_from_string(HTTP_PROTOCOLS[http])
    ws_protocol_class = import_from_string(WS_PROTOCOLS[ws])

    if isinstance(loop, str):
        loop_setup = import_from_string(LOOP_SETUPS[loop])
        loop = loop_setup()

    try:
        app = import_from_string(app)
    except ImportFromStringError as exc:
        click.echo("Error loading ASGI app. %s" % exc)
        sys.exit(1)

    if wsgi:
        app = WSGIMiddleware(app)
        ws_protocol_class = None
    if debug:
        app = DebugMiddleware(app)
    if logger.level <= logging.DEBUG:
        app = MessageLoggerMiddleware(app)
    if proxy_headers:
        app = ProxyHeadersMiddleware(app)

    connections = set()
    tasks = set()
    state = {"total_requests": 0}
    if keyfile or certfile:
        sslctx = create_ssl_context(
            keyfile=keyfile,
            certfile=certfile,
            ssl_version=ssl_version,
            cert_reqs=cert_reqs,
            ca_certs=ca_certs,
            ciphers=ciphers,
            enable_h2=getattr(http_protocol_class, "http2"),
        )
    else:
        sslctx = None

    def create_protocol():
        return http_protocol_class(
            app=app,
            loop=loop,
            logger=logger,
            access_log=access_log,
            connections=connections,
            tasks=tasks,
            state=state,
            ws_protocol_class=ws_protocol_class,
            root_path=root_path,
            limit_concurrency=limit_concurrency,
            timeout_keep_alive=timeout_keep_alive,
        )

    server = Server(
        app=app,
        host=host,
        port=port,
        uds=uds,
        sock=sock,
        logger=logger,
        loop=loop,
        connections=connections,
        tasks=tasks,
        state=state,
        limit_max_requests=limit_max_requests,
        create_protocol=create_protocol,
        on_tick=http_protocol_class.tick,
        install_signal_handlers=install_signal_handlers,
        ready_event=ready_event,
        ssl=sslctx,
    )
    server.run()


class Server:
    def __init__(
        self,
        app,
        host,
        port,
        uds,
        sock,
        logger,
        loop,
        connections,
        tasks,
        state,
        limit_max_requests,
        create_protocol,
        on_tick,
        install_signal_handlers,
        ready_event,
        ssl,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.uds = uds
        self.sock = sock
        self.logger = logger
        self.loop = loop
        self.connections = connections
        self.tasks = tasks
        self.state = state
        self.limit_max_requests = limit_max_requests
        self.create_protocol = create_protocol
        self.on_tick = on_tick
        self.install_signal_handlers = install_signal_handlers
        self.ready_event = ready_event
        self.should_exit = False
        self.pid = os.getpid()
        self.ssl = ssl

    def set_signal_handlers(self):
        if not self.install_signal_handlers:
            return

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
        if self.ready_event is not None:
            self.ready_event.set()
        self.loop.run_forever()

    async def create_server(self):
        if self.sock is not None:
            # Use an existing socket.
            self.server = await self.loop.create_server(
                self.create_protocol, sock=self.sock, ssl=self.ssl
            )
            message = "Uvicorn running on socket %s (Press CTRL+C to quit)"
            self.logger.info(message % str(self.sock.getsockname()))

        elif self.uds is not None:
            # Create a socket using UNIX domain socket.
            self.server = await self.loop.create_unix_server(
                self.create_protocol, path=self.uds, ssl=self.ssl
            )
            message = "Uvicorn running on unix socket %s (Press CTRL+C to quit)"
            self.logger.info(message % self.uds)

        else:
            # Standard case. Create a socket from a host/port pair.
            self.server = await self.loop.create_server(
                self.create_protocol, host=self.host, port=self.port, ssl=self.ssl
            )
            message = "Uvicorn running on http://%s:%d (Press CTRL+C to quit)"
            self.logger.info(message % (self.host, self.port))

    async def tick(self):
        should_limit_requests = self.limit_max_requests is not None

        while not self.should_exit:
            if (
                should_limit_requests
                and self.state["total_requests"] >= self.limit_max_requests
            ):
                break
            self.on_tick()
            await asyncio.sleep(1)

        self.logger.info("Stopping server process [{}]".format(self.pid))
        self.server.close()
        await self.server.wait_closed()
        for connection in list(self.connections):
            connection.shutdown()

        await asyncio.sleep(0.1)
        if self.connections:
            self.logger.info("Waiting for connections to close.")
            while self.connections:
                await asyncio.sleep(0.1)
        if self.tasks:
            self.logger.info("Waiting for background tasks to complete.")
            while self.tasks:
                await asyncio.sleep(0.1)

        self.loop.stop()


if __name__ == "__main__":
    main()
