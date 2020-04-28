import os
import signal
import time
from pathlib import Path

import pytest

from uvicorn.config import Config
from uvicorn.supervisors.watchgodreload import WatchGodReload

from . import WATCHED_FILES


def run(sockets):
    pass


def test_watchgodreload(certfile_and_keyfile):
    config = Config(app=None)
    reloader = WatchGodReload(config, target=run, sockets=[])
    reloader.signal_handler(sig=signal.SIGINT, frame=None)
    reloader.run()


@pytest.mark.parametrize("filename", WATCHED_FILES)
def test_should_reload_when_file_is_changed(tmpdir, filename):
    update_file = Path(tmpdir) / filename
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = WatchGodReload(config, target=run, sockets=[])
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


@pytest.mark.parametrize("filename", [(".dotted"), ("main.pyc")])
def test_should_not_reload_when_dot_or_pyc_file_is_changed(filename, tmpdir):
    update_file = Path(tmpdir) / filename
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = WatchGodReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        time.sleep(0.1)
        update_file.touch()
        assert not reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
