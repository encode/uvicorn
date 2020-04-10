import socket

import pytest

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


async def asgi3app(scope, receive, send):
    pass


def asgi2app(scope):
    async def asgi(receive, send):
        raise RuntimeError("Something went wrong")

    return asgi


asgi_scope_data = [
    (asgi3app, "asgi3", {"asgi": {"version": "3.0", "spec_version": "2.1"}}),
    (asgi2app, "asgi2", {"asgi": {"version": "2.0", "spec_version": "2.1"}}),
]


@pytest.mark.parametrize(
    "asgi2or3_app, expected_interface, expected_scope", asgi_scope_data
)
def test_interface_config(asgi2or3_app, expected_interface, expected_scope):
    config = Config(app=asgi2or3_app)
    config.load()
    assert config.interface == expected_interface
