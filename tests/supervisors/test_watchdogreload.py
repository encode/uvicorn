import os
import signal
import time
from pathlib import Path

from uvicorn.config import Config
from uvicorn.main import Server
from uvicorn.supervisors.watchdogreload import WatchdogReload


def run(sockets):
    pass


def test_statreload(certfile_and_keyfile):
    config = Config(app=None)
    reloader = WatchdogReload(config, target=run, sockets=[])
    reloader.signal_handler(sig=signal.SIGINT, frame=None)
    reloader.run()


def test_should_reload(tmpdir):
    update_file = Path(os.path.join(str(tmpdir), "example.py"))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = WatchdogReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        update_file.touch()
        time.sleep(0.5)
        assert reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
