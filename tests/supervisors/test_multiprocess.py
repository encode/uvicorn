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
    supervisor.handle_exit(sig=signal.SIGINT, frame=None)
    supervisor.run()


def test_multiprocess_run_term():
    """
    A basic sanity check.

    Simply run the supervisor against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=None, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.handle_term(sig=signal.SIGTERM, frame=None)
    supervisor.run()
