import os
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


def test_env_file(env_file):
    config = Config(app=asgi_app, env_file=env_file)
    config.load()
    assert bool(os.environ.get("KEY_TRUE"))
    assert not bool(os.environ.get("KEY_FALSE"))
    assert os.environ.get("KEY_NOT_EXISTS") is None
    # you'd love that a beefy desktop !
    assert int(os.environ.get("WEB_CONCURRENCY")) == 2048
    assert config.workers == 2048


def test_reload_dir(tmp_path):
    config = Config(app=asgi_app, reload_dirs=tmp_path)
    config.load()
    assert config.reload_dirs == tmp_path


def test_forwarded_allow_ips():
    config = Config(app=asgi_app, forwarded_allow_ips="192.168.0.1")
    config.load()
    assert config.forwarded_allow_ips == "192.168.0.1"


@pytest.mark.parametrize("use_colors", [(True), (False)])
def test_log_config_use_colors(use_colors):
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"default": {}, "access": {}},
    }
    config = Config(app=asgi_app, log_config=log_config, use_colors=use_colors)
    config.load()
    assert config.use_colors == use_colors


def test_log_config_inifile(ini_log_config):
    config = Config(app=asgi_app, log_config=ini_log_config)
    config.load()
    assert config

