import importlib
import os
from unittest import mock

import pytest
from click.testing import CliRunner

from uvicorn.main import main as cli

HEADERS = "Content-Security-Policy:default-src 'self'; script-src https://example.com"
main = importlib.import_module("uvicorn.main")


def test_cli_headers():
    runner = CliRunner()

    with mock.patch.object(main, "run") as mock_run:
        result = runner.invoke(cli, ["tests.test_cli:App", "--header", HEADERS])

    assert result.output == ""
    assert result.exit_code == 0
    mock_run.assert_called_once()
    assert mock_run.call_args[1]["headers"] == [
        [
            "Content-Security-Policy",
            "default-src 'self'; script-src https://example.com",
        ]
    ]


class App:
    pass


@pytest.fixture()
def load_env_h11_protocol():
    old_environ = dict(os.environ)
    os.environ["UVICORN_HTTP"] = "h11"
    yield
    os.environ.clear()
    os.environ.update(old_environ)


def test_env_variables(load_env_h11_protocol: None):
    runner = CliRunner(env=os.environ)
    with mock.patch.object(main, "run") as mock_run:
        runner.invoke(cli, ["tests.test_cli:App"])
        _, kwargs = mock_run.call_args
        assert kwargs["http"] == "h11"


def test_mistmatch_env_variables(load_env_h11_protocol: None):
    runner = CliRunner(env=os.environ)
    with mock.patch.object(main, "run") as mock_run:
        runner.invoke(cli, ["tests.test_cli:App", "--http=httptools"])
        _, kwargs = mock_run.call_args
        assert kwargs["http"] == "httptools"
