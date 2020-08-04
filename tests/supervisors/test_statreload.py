import os
import signal
import time
from pathlib import Path

from uvicorn.config import Config
from uvicorn.supervisors.statreload import StatReload


def run(sockets):
    pass


def test_statreload():
    """
    A basic sanity check.

    Simply run the reloader against a no-op server, and signal for it to
    quit immediately.
    """
    config = Config(app=None, reload=True)
    reloader = StatReload(config, target=run, sockets=[])
    reloader.signal_handler(sig=signal.SIGINT, frame=None)
    reloader.run()


def test_should_reload(tmpdir):
    update_file = Path(os.path.join(str(tmpdir), "example.py"))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = StatReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        time.sleep(0.1)
        update_file.touch()
        assert reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)


def test_should_reload_after_exception(tmpdir):
    update_file = Path(os.path.join(str(tmpdir), "example.py"))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = StatReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        time.sleep(1)
        with open(update_file, "w") as f:
            f.write("this will certainly raise a syntax error!")
        time.sleep(1)
        assert reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
