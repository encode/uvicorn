from socket import socket
from typing import List

from asgiref.typing import ASGIReceiveCallable, ASGISendCallable, Scope

from uvicorn.config import Config
from uvicorn.subprocess import subprocess_started


async def app(
    scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable
) -> None:
    pass


def test_subprocess_started() -> None:
    config = Config(app=app)
    config.load()

    def run_sockets(sockets: List[socket]):
        ...

    subprocess_started(config, run_sockets, [])
