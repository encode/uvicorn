import asyncio
import inspect
import logging
import socket
import ssl
import sys
from typing import List, Tuple

from uvicorn.importer import ImportFromStringError, import_from_string
from uvicorn.middleware.asgi2 import ASGI2Middleware
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
    "auto": "uvicorn.lifespan.on:LifespanOn",
    "on": "uvicorn.lifespan.on:LifespanOn",
    "off": "uvicorn.lifespan.off:LifespanOff",
}
LOOP_SETUPS = {
    "auto": "uvicorn.loops.auto:auto_loop_setup",
    "asyncio": "uvicorn.loops.asyncio:asyncio_setup",
    "uvloop": "uvicorn.loops.uvloop:uvloop_setup",
}
INTERFACES = ["auto", "asgi3", "asgi2", "wsgi"]

# Fallback to 'ssl.PROTOCOL_SSLv23' in order to support Python < 3.5.3.
SSL_PROTOCOL_VERSION = getattr(ssl, "PROTOCOL_TLS", ssl.PROTOCOL_SSLv23)


def get_logger(log_level):
    if isinstance(log_level, str):
        log_level = LOG_LEVELS[log_level]
    logging.basicConfig(format="%(levelname)s: %(message)s", level=log_level)
    logger = logging.getLogger("uvicorn")
    logger.setLevel(log_level)
    return logger


def create_ssl_context(certfile, keyfile, ssl_version, cert_reqs, ca_certs, ciphers):
    ctx = ssl.SSLContext(ssl_version)
    ctx.load_cert_chain(certfile, keyfile)
    ctx.verify_mode = cert_reqs
    if ca_certs:
        ctx.load_verify_locations(ca_certs)
    if ciphers:
        ctx.set_ciphers(ciphers)
    return ctx


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
        lifespan="auto",
        log_level="info",
        logger=None,
        access_log=True,
        interface="auto",
        debug=False,
        reload=False,
        reload_dirs=None,
        workers=1,
        proxy_headers=False,
        root_path="",
        limit_concurrency=None,
        limit_max_requests=None,
        timeout_keep_alive=5,
        timeout_notify=30,
        callback_notify=None,
        ssl_keyfile=None,
        ssl_certfile=None,
        ssl_version=SSL_PROTOCOL_VERSION,
        ssl_cert_reqs=ssl.CERT_NONE,
        ssl_ca_certs=None,
        ssl_ciphers="TLSv1",
        headers=None,
    ):
        self.app = app
        self.host = host
        self.port = port
        self.uds = uds
        self.fd = fd
        self.loop = loop
        self.http = http
        self.ws = ws
        self.lifespan = lifespan
        self.log_level = log_level
        self.logger = logger
        self.access_log = access_log
        self.interface = interface
        self.debug = debug
        self.reload = reload
        self.workers = workers
        self.proxy_headers = proxy_headers
        self.root_path = root_path
        self.limit_concurrency = limit_concurrency
        self.limit_max_requests = limit_max_requests
        self.timeout_keep_alive = timeout_keep_alive
        self.timeout_notify = timeout_notify
        self.callback_notify = callback_notify
        self.ssl_keyfile = ssl_keyfile
        self.ssl_certfile = ssl_certfile
        self.ssl_version = ssl_version
        self.ssl_cert_reqs = ssl_cert_reqs
        self.ssl_ca_certs = ssl_ca_certs
        self.ssl_ciphers = ssl_ciphers
        self.headers = headers if headers else []  # type: List[str]
        self.encoded_headers = None  # type: List[Tuple[bytes, bytes]]

        if reload_dirs is None:
            self.reload_dirs = sys.path
        else:
            self.reload_dirs = reload_dirs

        self.loaded = False

    @property
    def is_ssl(self) -> bool:
        return self.ssl_keyfile or self.ssl_certfile

    def load(self):
        assert not self.loaded

        if self.is_ssl:
            self.ssl = create_ssl_context(
                keyfile=self.ssl_keyfile,
                certfile=self.ssl_certfile,
                ssl_version=self.ssl_version,
                cert_reqs=self.ssl_cert_reqs,
                ca_certs=self.ssl_ca_certs,
                ciphers=self.ssl_ciphers,
            )
        else:
            self.ssl = None

        encoded_headers = [
            (key.lower().encode("latin1"), value.encode("latin1"))
            for key, value in self.headers
        ]
        self.encoded_headers = (
            encoded_headers
            if b"server" in dict(encoded_headers)
            else [(b"server", b"uvicorn")] + encoded_headers
        )  # type: List[Tuple[bytes, bytes]]

        if isinstance(self.http, str):
            self.http_protocol_class = import_from_string(HTTP_PROTOCOLS[self.http])
        else:
            self.http_protocol_class = self.http

        if isinstance(self.ws, str):
            self.ws_protocol_class = import_from_string(WS_PROTOCOLS[self.ws])
        else:
            self.ws_protocol_class = self.ws

        self.lifespan_class = import_from_string(LIFESPAN[self.lifespan])

        try:
            self.loaded_app = import_from_string(self.app)
        except ImportFromStringError as exc:
            self.logger_instance.error("Error loading ASGI app. %s" % exc)
            sys.exit(1)

        if self.interface == "auto":
            if inspect.isclass(self.loaded_app):
                use_asgi_3 = hasattr(self.loaded_app, "__await__")
            elif inspect.isfunction(self.loaded_app):
                use_asgi_3 = asyncio.iscoroutinefunction(self.loaded_app)
            else:
                call = getattr(self.loaded_app, "__call__", None)
                use_asgi_3 = asyncio.iscoroutinefunction(call)
            self.interface = "asgi3" if use_asgi_3 else "asgi2"

        if self.interface == "wsgi":
            self.loaded_app = WSGIMiddleware(self.loaded_app)
            self.ws_protocol_class = None
        elif self.interface == "asgi2":
            self.loaded_app = ASGI2Middleware(self.loaded_app)

        if self.debug:
            self.loaded_app = DebugMiddleware(self.loaded_app)
        if self.logger_instance.level <= logging.DEBUG:
            self.loaded_app = MessageLoggerMiddleware(self.loaded_app)
        if self.proxy_headers:
            self.loaded_app = ProxyHeadersMiddleware(self.loaded_app)

        self.loaded = True

    def setup_event_loop(self):
        loop_setup = import_from_string(LOOP_SETUPS[self.loop])
        loop_setup()

    def bind_socket(self):
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.host, self.port))
        sock.set_inheritable(True)
        message = "Uvicorn running on %s://%s:%d (Press CTRL+C to quit)"
        protocol_name = "https" if self.is_ssl else "http"
        self.logger_instance.info(message % (protocol_name, self.host, self.port))
        return sock

    @property
    def logger_instance(self):
        if self.logger is not None:
            return self.logger
        return get_logger(self.log_level)
