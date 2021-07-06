import importlib
import sys
import textwrap
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from uvicorn.main import main as cli

HEADERS = "Content-Security-Policy:default-src 'self'; script-src https://example.com"
main = importlib.import_module("uvicorn.main")


class App:
    pass


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


@pytest.mark.skipif(sys.platform == "win32", reason="require unix-like system")
def test_load_app_before_event_loop(tmp_path: Path):
    runner = CliRunner()
    fp = tmp_path / "main.py"
    content = textwrap.dedent(
        """
        import asyncio

        print("Event loop running:", asyncio.get_event_loop().is_running(), end="")

        async def app(scope, receive, send):
            pass
        """
    )
    fp.write_text(content)
    with mock.patch("uvicorn.server.Server.serve"):
        result = runner.invoke(cli, ["main:app", "--app-dir", tmp_path])
        assert "Event loop running: False" in result.stdout
