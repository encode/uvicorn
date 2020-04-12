import os
import socket
import sys

import pytest

from uvicorn import protocols
from uvicorn.config import LOG_LEVELS, Config
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


log_lvl_passed = [(k) for k, v in LOG_LEVELS.items()] + [
    (v) for k, v in LOG_LEVELS.items()
]


@pytest.mark.parametrize("log_lvl_passed", log_lvl_passed)
def test_log_level(log_lvl_passed,):
    config = Config(app=asgi_app, log_level=log_lvl_passed)
    config.load()
    assert config.log_level == log_lvl_passed


def test_log_access():
    config = Config(app=asgi_app, access_log=False)
    config.load()
    assert not config.access_log


def test_fail_asgi_app_import_and_exit():
    asgi_app_wrong = ""
    config = Config(app=asgi_app_wrong)
    with pytest.raises(SystemExit) as pytest_wrapped_e:
        config.load()
    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


def test_should_reload_property():
    config = Config(app="tests.test_config:asgi_app", reload=True)
    config.load()
    assert config.should_reload


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Skipping unix domain socket test on Windows and pypy",
)
def test_config_unix_domain_socket(socket_file):
    uds, _, _ = socket_file
    config = Config(app=asgi_app, uds=uds)
    config.load()
    assert config.uds == uds


@pytest.mark.skipif(
    sys.platform.startswith("win"), reason="Skipping file descriptor test on Windows"
)
def test_config_file_descriptor(socket_file):
    _, _, fd = socket_file

    config = Config(app=asgi_app, fd=fd)
    config.load()
    assert config.fd == fd


# def test_config_rebind_socket():
#     sock = socket.socket()
#     config = Config(asgi_app)
#     with pytest.raises(SystemExit) as pytest_wrapped_e:
#         sock.bind((config.host, config.port))
#         config.bind_socket()
#     assert pytest_wrapped_e.type == SystemExit
#     assert pytest_wrapped_e.value.code == 1
#     sock.close()
