import socket

import pytest

from tests.protocols.test_http import (
    HTTP_PROTOCOLS,
    SIMPLE_GET_REQUEST,
    get_connected_protocol,
)
from uvicorn import protocols
from uvicorn.config import Config
from uvicorn.middleware.debug import DebugMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from uvicorn.middleware.wsgi import WSGIMiddleware


async def asgi_app():
    pass  # pragma: nocover


def wsgi_app():
    pass  # pragma: nocover


def test_debug_app():
    config = Config(app=asgi_app, debug=True, proxy_headers=False)
    config.load()

    assert config.debug is True
    assert isinstance(config.loaded_app, DebugMiddleware)


def test_wsgi_app():
    config = Config(app=wsgi_app, interface="wsgi", proxy_headers=False)
    config.load()

    assert isinstance(config.loaded_app, WSGIMiddleware)
    assert config.interface == "wsgi"


def test_proxy_headers():
    config = Config(app=asgi_app)
    config.load()

    assert config.proxy_headers is True
    assert isinstance(config.loaded_app, ProxyHeadersMiddleware)


def test_app_unimportable():
    config = Config(app="no.such:app")
    with pytest.raises(ImportError):
        config.load()


def test_concrete_http_class():
    config = Config(app=asgi_app, http=protocols.http.h11_impl.H11Protocol)
    config.load()
    assert config.http_protocol_class is protocols.http.h11_impl.H11Protocol


def test_socket_bind():
    config = Config(app=asgi_app)
    config.load()

    assert isinstance(config.bind_socket(), socket.socket)


def test_ssl_config(certfile_and_keyfile):
    certfile, keyfile = certfile_and_keyfile
    config = Config(app=asgi_app, ssl_certfile=certfile, ssl_keyfile=keyfile)
    config.load()

    assert config.is_ssl is True


def asgi2_app(scope):
    async def asgi(receive, send):
        pass

    return asgi


@pytest.mark.parametrize(
    "app, expected_interface", [(asgi_app, "3.0",), (asgi2_app, "2.0",),]
)
def test_asgi_version(app, expected_interface):
    config = Config(app=app)
    config.load()
    assert config.asgi_version == expected_interface
