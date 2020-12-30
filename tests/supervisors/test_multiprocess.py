import multiprocessing
import signal

from uvicorn import Config
from uvicorn.supervisors import Multiprocess


def run(*args, **kwargs):
    pass


def test_multiprocess_run():
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=None, workers=2)
    shutdown_event = multiprocessing.Event()
    supervisor = Multiprocess(
        config,
        target=run,
        sockets=[],
        shutdown_event=shutdown_event,
        reload_event=None,
    )
    supervisor.multiprocess_signal_handler(sig=signal.SIGINT, frame=None)
    supervisor.run()
