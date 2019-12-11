import logging
import os
import signal
import sys
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


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Skipping reload test on Windows, due to low mtime resolution.",
)
def test_should_reload(tmpdir):
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
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
        logger.debug(f"before reload: {os.path.getmtime(update_file)}")
        update_file.touch()
        logger.debug(f"after reload: {os.path.getmtime(update_file)}")
        assert reloader.should_restart()

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
