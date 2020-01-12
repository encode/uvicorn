import os
import signal
import time
from pathlib import Path

import pytest

from uvicorn.config import Config
from uvicorn.supervisors import StatReload


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
    """
    Basic test to reload when a .py file is updated.
    """
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


def test_should_respect_reload_dirs(tmpdir):
    """
    Test to verify that the reload_dirs config option is respected.
    """
    inner_path = os.path.join(str(tmpdir), "inner_dir", "inner.py")
    os.makedirs(os.path.dirname(inner_path), exist_ok=True)
    inner_update_file = Path(inner_path)
    inner_update_file.touch()

    outer_update_file = Path(os.path.join(str(tmpdir), "outer.py"))
    outer_update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True, reload_dirs=["inner_dir"])
        reloader = StatReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        time.sleep(0.1)
        inner_update_file.touch()
        assert reloader.should_restart()

        reloader.restart()

        assert not reloader.should_restart()
        time.sleep(0.1)
        outer_update_file.touch()
        assert not reloader.should_restart()

        reloader.shutdown()
    finally:
        os.chdir(working_dir)


def test_should_respect_reload_types(tmpdir):
    """
    Test to verify that the reload_types config option is respected.
    """
    py_update_file = Path(os.path.join(str(tmpdir), "example.py"))
    py_update_file.touch()

    elm_update_file = Path(os.path.join(str(tmpdir), "example.elm"))
    elm_update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True, reload_types=[".py", ".elm"])
        reloader = StatReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        time.sleep(0.1)
        py_update_file.touch()
        assert reloader.should_restart()

        reloader.restart()

        assert not reloader.should_restart()
        time.sleep(0.1)
        elm_update_file.touch()
        assert reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
