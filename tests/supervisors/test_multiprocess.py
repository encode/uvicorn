from __future__ import annotations

import signal
import socket
import sys
import threading
import time

import pytest

from uvicorn import Config
from uvicorn._types import ASGIReceiveCallable, ASGISendCallable, Scope
from uvicorn.supervisors import Multiprocess


async def app(scope: Scope, receive: ASGIReceiveCallable, send: ASGISendCallable) -> None:
    pass  # pragma: no cover


def run(sockets: list[socket.socket] | None) -> None:
    while True:
        time.sleep(1)


@pytest.mark.skipif(sys.platform == "win32", reason="In Windows, Ctrl+C/Ctrl+Break will sent to the parent process.")
def test_multiprocess_run() -> None:
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    supervisor.signal_queue.append(signal.SIGINT)


@pytest.mark.skipif(sys.platform == "win32", reason="In Windows, Ctrl+C/Ctrl+Break will sent to the parent process.")
def test_multiprocess_health_check() -> None:
    """
    Ensure that the health check works as expected.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    time.sleep(1)
    process = supervisor.processes[0]
    process.kill()
    assert not process.is_alive()
    time.sleep(1)
    for p in supervisor.processes:
        assert p.is_alive()
    supervisor.signal_queue.append(signal.SIGINT)
    supervisor.join_all()


@pytest.mark.skipif(sys.platform == "win32", reason="In Windows, Ctrl+C/Ctrl+Break will sent to the parent process.")
def test_multiprocess_sigterm() -> None:
    """
    Ensure that the SIGTERM signal is handled as expected.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    time.sleep(1)
    supervisor.signal_queue.append(signal.SIGTERM)
    supervisor.join_all()


@pytest.mark.skipif(sys.platform == "win32", reason="In Windows, Ctrl+C/Ctrl+Break will sent to the parent process.")
@pytest.mark.skipif(not hasattr(signal, "SIGBREAK"), reason="platform unsupports SIGBREAK")
def test_multiprocess_sigbreak() -> None:
    """
    Ensure that the SIGBREAK signal is handled as expected.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    time.sleep(1)
    supervisor.signal_queue.append(getattr(signal, "SIGBREAK"))
    supervisor.join_all()


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="platform unsupports SIGHUP")
def test_multiprocess_sighup() -> None:
    """
    Ensure that the SIGHUP signal is handled as expected.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    time.sleep(1)
    pids = [p.pid for p in supervisor.processes]
    supervisor.signal_queue.append(signal.SIGHUP)
    time.sleep(1)
    assert pids != [p.pid for p in supervisor.processes]
    supervisor.signal_queue.append(signal.SIGINT)
    supervisor.join_all()


@pytest.mark.skipif(not hasattr(signal, "SIGTTIN"), reason="platform unsupports SIGTTIN")
def test_multiprocess_sigttin() -> None:
    """
    Ensure that the SIGTTIN signal is handled as expected.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    supervisor.signal_queue.append(signal.SIGTTIN)
    time.sleep(1)
    assert len(supervisor.processes) == 3
    supervisor.signal_queue.append(signal.SIGINT)
    supervisor.join_all()


@pytest.mark.skipif(not hasattr(signal, "SIGTTOU"), reason="platform unsupports SIGTTOU")
def test_multiprocess_sigttou() -> None:
    """
    Ensure that the SIGTTOU signal is handled as expected.
    """
    config = Config(app=app, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    threading.Thread(target=supervisor.run, daemon=True).start()
    supervisor.signal_queue.append(signal.SIGTTOU)
    time.sleep(1)
    assert len(supervisor.processes) == 1
    supervisor.signal_queue.append(signal.SIGTTOU)
    time.sleep(1)
    assert len(supervisor.processes) == 1
    supervisor.signal_queue.append(signal.SIGINT)
    supervisor.join_all()
