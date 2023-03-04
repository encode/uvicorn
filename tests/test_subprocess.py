import socket
from typing import TYPE_CHECKING, List
from unittest.mock import patch

from uvicorn._subprocess import SpawnProcess, get_subprocess, subprocess_started
from uvicorn.config import Config

if TYPE_CHECKING:
    from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, Scope


def server_run(sockets: List[socket.socket]):  # pragma: no cover
    ...


async def app(
    scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
) -> None:  # pragma: no cover
    ...


def test_get_subprocess() -> None:
    fdsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    fd = fdsock.fileno()
    config = Config(app=app, fd=fd)
    config.load()

    process = get_subprocess(config, server_run, [fdsock])
    assert isinstance(process, SpawnProcess)

    fdsock.close()


def test_subprocess_started() -> None:
    fdsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    fd = fdsock.fileno()
    config = Config(app=app, fd=fd)
    config.load()

    with patch("tests.test_subprocess.server_run") as mock_run:
        with patch.object(config, "configure_logging") as mock_config_logging:
            subprocess_started(config, server_run, [fdsock], None)
            mock_run.assert_called_once()
            mock_config_logging.assert_called_once()

    fdsock.close()
