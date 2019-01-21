from uvicorn.importer import import_from_string, ImportFromStringError
from uvicorn.middleware.debug import DebugMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from uvicorn.middleware.message_logger import MessageLoggerMiddleware
from uvicorn.middleware.wsgi import WSGIMiddleware
import click
import logging
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
    "h11": "uvicorn.protocols.http.h11_impl:H11Protocol",
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


def get_logger(log_level):
    if isinstance(log_level, str):
        log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    logger = logging.getLogger("uvicorn")
    logger.setLevel(log_level)
    return logger


class Config:
    def __init__(
        self,
        app,
        host="127.0.0.1",
        port=8000,
        uds=None,
        fd=None,
        loop="auto",
        http="auto",
        ws="auto",
        log_level="info",
        logger=None,
        access_log=True,
        wsgi=False,
        debug=False,
        proxy_headers=False,
        root_path="",
        limit_concurrency=None,
        limit_max_requests=None,
        disable_lifespan=False,
        timeout_keep_alive=5,
        install_signal_handlers=True,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.uds = uds
        self.fd = fd
        self.loop = loop
        self.http = http
        self.ws = ws
        self.log_level = log_level
        self.logger = logger
        self.access_log = access_log
        self.wsgi = wsgi
        self.debug = debug
        self.proxy_headers = proxy_headers
        self.root_path = root_path
        self.limit_concurrency = limit_concurrency
        self.limit_max_requests = limit_max_requests
        self.disable_lifespan = disable_lifespan
        self.timeout_keep_alive = timeout_keep_alive
        self.install_signal_handlers = install_signal_handlers

        if fd is None:
            self.sock = None
        else:
            self.host = None
            self.port = None
            self.sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)

        if self.logger is None:
            self.logger = get_logger(log_level)
        else:
            assert log_level == "info", "Cannot set both 'logger' and 'log_level'"

        if isinstance(http, str):
            self.http_protocol_class = import_from_string(HTTP_PROTOCOLS[http])
        else:
            self.http_protocol_class = http

        if isinstance(ws, str):
            self.ws_protocol_class = import_from_string(WS_PROTOCOLS[ws])
        else:
            self.ws_protocol_class = ws

        if isinstance(self.loop, str):
            loop_setup = import_from_string(LOOP_SETUPS[loop])
            self.loop = loop_setup()

        try:
            self.app = import_from_string(self.app)
        except ImportFromStringError as exc:
            click.echo("Error loading ASGI app. %s" % exc)
            sys.exit(1)

        if self.wsgi:
            self.app = WSGIMiddleware(self.app)
            ws_protocol_class = None
        if self.debug:
            self.app = DebugMiddleware(self.app)
        if self.logger.level <= logging.DEBUG:
            self.app = MessageLoggerMiddleware(self.app)
        if self.proxy_headers:
            self.app = ProxyHeadersMiddleware(self.app)
