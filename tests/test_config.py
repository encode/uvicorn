import json
import socket
from copy import deepcopy

import pytest
import yaml

from uvicorn.config import LOGGING_CONFIG, Config
from uvicorn.middleware.debug import DebugMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
from uvicorn.middleware.wsgi import WSGIMiddleware
from uvicorn.protocols.http.h11_impl import H11Protocol


@pytest.fixture
def mocked_logging_config_module(mocker):
    return mocker.patch("logging.config")


@pytest.fixture(scope="function")
def logging_config():
    return deepcopy(LOGGING_CONFIG)


@pytest.fixture
def json_logging_config(logging_config):
    return json.dumps(logging_config)


@pytest.fixture
def yaml_logging_config(logging_config):
    return yaml.dump(logging_config)


async def asgi_app(scope, receive, send):
    pass  # pragma: nocover


def wsgi_app(environ, start_response):
    pass  # pragma: nocover


def test_debug_app():
    config = Config(app=asgi_app, debug=True, proxy_headers=False)
    config.load()

    assert config.debug is True
    assert isinstance(config.loaded_app, DebugMiddleware)


@pytest.mark.parametrize(
    "app, expected_should_reload",
    [(asgi_app, False), ("tests.test_config:asgi_app", True)],
)
def test_config_should_reload_is_set(app, expected_should_reload):
    config_debug = Config(app=app, debug=True)
    assert config_debug.debug is True
    assert config_debug.should_reload is expected_should_reload

    config_reload = Config(app=app, reload=True)
    assert config_reload.reload is True
    assert config_reload.should_reload is expected_should_reload


def test_wsgi_app():
    config = Config(app=wsgi_app, interface="wsgi", proxy_headers=False)
    config.load()

    assert isinstance(config.loaded_app, WSGIMiddleware)
    assert config.interface == "wsgi"
    assert config.asgi_version == "3.0"


def test_proxy_headers():
    config = Config(app=asgi_app)
    config.load()

    assert config.proxy_headers is True
    assert isinstance(config.loaded_app, ProxyHeadersMiddleware)


def test_app_unimportable_module():
    config = Config(app="no.such:app")
    with pytest.raises(ImportError):
        config.load()


def test_app_unimportable_other(caplog):
    config = Config(app="tests.test_config:app")
    with pytest.raises(SystemExit):
        config.load()
    error_messages = [
        record.message
        for record in caplog.records
        if record.name == "uvicorn.error" and record.levelname == "ERROR"
    ]
    assert (
        'Error loading ASGI app. Attribute "app" not found in module "tests.test_config".'  # noqa: E501
        == error_messages.pop(0)
    )


def test_app_factory():
    def create_app():
        return asgi_app

    config = Config(app=create_app, factory=True, proxy_headers=False)
    config.load()
    assert config.loaded_app is asgi_app

    # Flag missing.
    config = Config(app=create_app)
    with pytest.raises(SystemExit):
        config.load()

    # App not a no-arguments callable.
    config = Config(app=asgi_app, factory=True)
    with pytest.raises(SystemExit):
        config.load()


def test_concrete_http_class():
    config = Config(app=asgi_app, http=H11Protocol)
    config.load()
    assert config.http_protocol_class is H11Protocol


def test_socket_bind():
    config = Config(app=asgi_app)
    config.load()

    assert isinstance(config.bind_socket(), socket.socket)


def test_ssl_config(tls_ca_certificate_pem_path, tls_ca_certificate_private_key_path):
    config = Config(
        app=asgi_app,
        ssl_certfile=tls_ca_certificate_pem_path,
        ssl_keyfile=tls_ca_certificate_private_key_path,
    )
    config.load()

    assert config.is_ssl is True


def test_ssl_config_combined(tls_certificate_pem_path):
    config = Config(
        app=asgi_app,
        ssl_certfile=tls_certificate_pem_path,
    )
    config.load()

    assert config.is_ssl is True


def asgi2_app(scope):
    async def asgi(receive, send):
        pass

    return asgi


@pytest.mark.parametrize(
    "app, expected_interface", [(asgi_app, "3.0"), (asgi2_app, "2.0")]
)
def test_asgi_version(app, expected_interface):
    config = Config(app=app)
    config.load()
    assert config.asgi_version == expected_interface


@pytest.mark.parametrize(
    "use_colors, expected",
    [
        pytest.param(None, None, id="use_colors_not_provided"),
        pytest.param("invalid", None, id="use_colors_invalid_value"),
        pytest.param(True, True, id="use_colors_enabled"),
        pytest.param(False, False, id="use_colors_disabled"),
    ],
)
def test_log_config_default(mocked_logging_config_module, use_colors, expected):
    """
    Test that one can specify the use_colors option when using the default logging
    config.
    """
    config = Config(app=asgi_app, use_colors=use_colors)
    config.load()

    mocked_logging_config_module.dictConfig.assert_called_once_with(LOGGING_CONFIG)

    (provided_dict_config,), _ = mocked_logging_config_module.dictConfig.call_args
    assert provided_dict_config["formatters"]["default"]["use_colors"] == expected


def test_log_config_json(
    mocked_logging_config_module, logging_config, json_logging_config, mocker
):
    """
    Test that one can load a json config from disk.
    """
    mocked_open = mocker.patch(
        "uvicorn.config.open", mocker.mock_open(read_data=json_logging_config)
    )

    config = Config(app=asgi_app, log_config="log_config.json")
    config.load()

    mocked_open.assert_called_once_with("log_config.json")
    mocked_logging_config_module.dictConfig.assert_called_once_with(logging_config)


@pytest.mark.parametrize("config_filename", ["log_config.yml", "log_config.yaml"])
def test_log_config_yaml(
    mocked_logging_config_module,
    logging_config,
    yaml_logging_config,
    mocker,
    config_filename,
):
    """
    Test that one can load a yaml config from disk.
    """
    mocked_open = mocker.patch(
        "uvicorn.config.open", mocker.mock_open(read_data=yaml_logging_config)
    )

    config = Config(app=asgi_app, log_config=config_filename)
    config.load()

    mocked_open.assert_called_once_with(config_filename)
    mocked_logging_config_module.dictConfig.assert_called_once_with(logging_config)


def test_log_config_file(mocked_logging_config_module):
    """
    Test that one can load a configparser config from disk.
    """
    config = Config(app=asgi_app, log_config="log_config")
    config.load()

    mocked_logging_config_module.fileConfig.assert_called_once_with(
        "log_config", disable_existing_loggers=False
    )
