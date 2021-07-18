import importlib
from unittest import mock

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
