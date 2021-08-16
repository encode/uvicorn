import importlib
import platform
import sys
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

import uvicorn
from uvicorn.config import Config
from uvicorn.main import main as cli
from uvicorn.server import Server
from uvicorn.supervisors import ChangeReload, Multiprocess

HEADERS = "Content-Security-Policy:default-src 'self'; script-src https://example.com"
main = importlib.import_module("uvicorn.main")


def test_cli_print_version() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert (
        "Running uvicorn %s with %s %s on %s"
        % (
            uvicorn.__version__,
            platform.python_implementation(),
            platform.python_version(),
            platform.system(),
        )
    ) in result.output


def test_cli_headers() -> None:
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


def test_cli_call_server_run() -> None:
    runner = CliRunner()

    with mock.patch.object(Server, "run") as mock_run:
        result = runner.invoke(cli, ["tests.test_cli:App"])

    assert result.exit_code == 0
    mock_run.assert_called_once()


def test_cli_call_change_reload_run() -> None:
    runner = CliRunner()

    with mock.patch.object(Config, "bind_socket") as mock_bind_socket:
        with mock.patch.object(ChangeReload, "run") as mock_run:
            result = runner.invoke(cli, ["tests.test_cli:App", "--reload"])

    assert result.exit_code == 0
    mock_bind_socket.assert_called_once()
    mock_run.assert_called_once()


def test_cli_call_multiprocess_run() -> None:
    runner = CliRunner()

    with mock.patch.object(Config, "bind_socket") as mock_bind_socket:
        with mock.patch.object(Multiprocess, "run") as mock_run:
            result = runner.invoke(cli, ["tests.test_cli:App", "--workers=2"])

    assert result.exit_code == 0
    mock_bind_socket.assert_called_once()
    mock_run.assert_called_once()


@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like system")
def test_cli_uds(tmp_path: Path) -> None:
    runner = CliRunner()
    uds_file = tmp_path / "uvicorn.sock"
    uds_file.touch(exist_ok=True)

    with mock.patch.object(Config, "bind_socket") as mock_bind_socket:
        with mock.patch.object(Multiprocess, "run") as mock_run:
            result = runner.invoke(
                cli, ["tests.test_cli:App", "--workers=2", "--uds", str(uds_file)]
            )

    assert result.exit_code == 0
    assert result.output == ""
    mock_bind_socket.assert_called_once()
    mock_run.assert_called_once()
    assert not uds_file.exists()


def test_cli_incomplete_app_parameter() -> None:
    runner = CliRunner()

    result = runner.invoke(cli, ["tests.test_cli"])

    assert (
        'Error loading ASGI app. Import string "tests.test_cli" '
        'must be in format "<module>:<attribute>".'
    ) in result.output
    assert result.exit_code == 1


class App:
    pass
