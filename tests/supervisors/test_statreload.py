import os
import signal
import sys
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


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Skipping reload test on Windows, due to low mtime resolution.",
)
@pytest.mark.parametrize(
    "extensions,testfile,expected",
    [
        (None, "test.py", True),
        (None, "test.graphql", False),
        ([".py"], "test.py", True),
        ([".py", ".graphql"], "test.py", True),
        ([".py", ".graphql"], "test.graphql", True),
        ([".py", ".graphql"], "test.html", False),
    ],
)
def test_should_reload(extensions, testfile, expected, tmpdir):
    update_file = Path(os.path.join(str(tmpdir), testfile))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True, reload_extensions=extensions)
        reloader = StatReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()
        assert not reloader.should_restart()

        # This sleep is needed to avoid unreliable tests.
        # Relying on timing in tests is a bad idea but I'm not sure
        # how to do better in this case since we are actually testing
        # if StatReload's understanding of mtime is correct so we are
        # bound by it's precision.
        time.sleep(0.01)
        update_file.touch()
        assert reloader.should_restart() is expected

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
