import logging
import socket

import pytest

from uvicorn import protocols
from uvicorn.config import Config
from uvicorn.middleware.debug import DebugMiddleware
from uvicorn.middleware.wsgi import WSGIMiddleware


async def asgi_app():
    pass


def wsgi_app():
    pass


def test_debug_app():
    config = Config(app=asgi_app, debug=True)
    config.load()

    assert config.debug is True
    assert isinstance(config.loaded_app, DebugMiddleware)


def test_wsgi_app():
    config = Config(app=wsgi_app, interface="wsgi")
    config.load()

    assert isinstance(config.loaded_app, WSGIMiddleware)
    assert config.interface == "wsgi"


def test_proxy_headers():
    config = Config(app=asgi_app, proxy_headers=True)
    config.load()

    assert config.proxy_headers is True


def test_app_unimportable():
    config = Config(app="no.such:app")
    with pytest.raises(ImportError):
        config.load()


def test_concrete_http_class():
    config = Config(app=asgi_app, http=protocols.http.h11_impl.H11Protocol)
    config.load()
    assert config.http_protocol_class is protocols.http.h11_impl.H11Protocol


def test_logger():
    logger = logging.getLogger("just-for-tests")
    config = Config(app=asgi_app, logger=logger)
    config.load()

    assert config.logger is logger


def test_socket_bind():
    config = Config(app=asgi_app)
    config.load()

    assert isinstance(config.bind_socket(), socket.socket)


def test_ssl_config(certfile_and_keyfile):
    certfile, keyfile = certfile_and_keyfile
    config = Config(app=asgi_app, ssl_certfile=certfile.name, ssl_keyfile=keyfile.name)
    config.load()

    assert config.is_ssl is True
