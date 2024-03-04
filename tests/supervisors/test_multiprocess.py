from __future__ import annotations

import signal
import socket
import threading
import time
from typing import List, Optional

from uvicorn import Config
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.supervisors import Multiprocess


async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
    pass  # pragma: no cover


def run(sockets: list[socket.socket] | None) -> None:
    pass  # pragma: no cover


def stop_run(stop) -> None:
    while True:
        time.sleep(1)
        stop()


def test_multiprocess_run() -> None:
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(
        target=stop_run, args=(supervisor.handle_int,), daemon=True
    ).start()
    supervisor.run()
