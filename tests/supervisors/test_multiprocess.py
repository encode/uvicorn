import os
import signal

from uvicorn import Config
from uvicorn.supervisors import Multiprocess


def run(sockets):
    pass


def test_multiprocess_run():
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=None, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.signal_handler(sig=signal.SIGINT, frame=None)
    supervisor.run()


def test_multiprocess_run2():
    config = Config(app=None, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.startup()
    os.kill(supervisor.pid, signal.SIGINT)
    supervisor.shutdown()
