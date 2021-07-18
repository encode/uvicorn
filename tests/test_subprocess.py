from socket import socket
from typing import List
from unittest.mock import patch

from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, Scope

from uvicorn.config import Config
from uvicorn.subprocess import subprocess_started


def server_run(sockets: List[socket]):
    ...


async def app(
    scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
) -> None:
    pass


def test_get_subprocess() -> None:
    ...


def test_subprocess_started() -> None:
    config = Config(app=app)
    config.load()

    with patch("tests.test_subprocess.server_run") as mock_run:
        with patch.object(config, "configure_logging") as mock_config_logging:
            subprocess_started(config, server_run, [], None)
            mock_run.assert_called_once()
            mock_config_logging.assert_called_once()
