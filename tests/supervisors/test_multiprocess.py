import signal
import socket
from typing import List, Optional

from uvicorn import Config
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.supervisors import Multiprocess


async def app(
    scope: "Scope", receive: "ASGIReceiveCallable", send: "ASGISendCallable"
) -> None:
    pass  # pragma: no cover


def run(sockets: Optional[List[socket.socket]]) -> None:
    pass  # pragma: no cover


def test_multiprocess_run() -> None:
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.handle_int()
    supervisor.run()
