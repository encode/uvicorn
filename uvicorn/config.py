import logging
import sys

from uvicorn.importer import ImportFromStringError, import_from_string
from uvicorn.middleware.debug import DebugMiddleware
from uvicorn.middleware.message_logger import MessageLoggerMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from uvicorn.middleware.wsgi import WSGIMiddleware

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
LIFESPAN = {
    "auto": "uvicorn.lifespan.auto:LifespanAuto",
    "on": "uvicorn.lifespan.on:LifespanOn",
    "off": "uvicorn.lifespan.off:LifespanOff",
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
        sockets=None,
        loop="auto",
        http="auto",
        ws="auto",
        lifespan="auto",
        log_level="info",
        logger=None,
        access_log=True,
        wsgi=False,
        debug=False,
        proxy_headers=False,
        root_path="",
        limit_concurrency=None,
        limit_max_requests=None,
        timeout_keep_alive=5,
        timeout_notify=30,
        callback_notify=None,
        install_signal_handlers=True,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.uds = uds
        self.fd = fd
        self.sockets = sockets
        self.loop = loop
        self.http = http
        self.ws = ws
        self.lifespan = lifespan
        self.log_level = log_level
        self.logger = logger
        self.access_log = access_log
        self.wsgi = wsgi
        self.debug = debug
        self.proxy_headers = proxy_headers
        self.root_path = root_path
        self.limit_concurrency = limit_concurrency
        self.limit_max_requests = limit_max_requests
        self.timeout_keep_alive = timeout_keep_alive
        self.timeout_notify = timeout_notify
        self.callback_notify = callback_notify

        self.loaded = False

    def load(self):
        assert not self.loaded

        if self.logger is None:
            self.logger_instance = get_logger(self.log_level)
        else:
            self.logger_instance = self.logger

        if isinstance(self.http, str):
            self.http_protocol_class = import_from_string(HTTP_PROTOCOLS[self.http])
        else:
            self.http_protocol_class = self.http

        if isinstance(self.ws, str):
            self.ws_protocol_class = import_from_string(WS_PROTOCOLS[self.ws])
        else:
            self.ws_protocol_class = self.ws

        self.lifespan_class = import_from_string(LIFESPAN[self.lifespan])

        if isinstance(self.loop, str):
            loop_setup = import_from_string(LOOP_SETUPS[self.loop])
            self.loop_instance = loop_setup()
        else:
            self.loop_instance = self.loop

        try:
            self.loaded_app = import_from_string(self.app)
        except ImportFromStringError as exc:
            self.logger_instance.error("Error loading ASGI app. %s" % exc)
            sys.exit(1)

        if self.wsgi:
            self.loaded_app = WSGIMiddleware(self.loaded_app)
            self.ws_protocol_class = None
        if self.debug:
            self.loaded_app = DebugMiddleware(self.loaded_app)
        if self.logger_instance.level <= logging.DEBUG:
            self.loaded_app = MessageLoggerMiddleware(self.loaded_app)
        if self.proxy_headers:
            self.loaded_app = ProxyHeadersMiddleware(self.loaded_app)

        self.loaded = True
