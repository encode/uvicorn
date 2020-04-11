import os
import signal
import time
from pathlib import Path

import pytest

from uvicorn.config import Config
from uvicorn.supervisors.watchgodreload import WatchGodReload


def run(sockets):
    pass


def test_statreload(certfile_and_keyfile):
    config = Config(app=None)
    reloader = WatchGodReload(config, target=run, sockets=[])
    reloader.signal_handler(sig=signal.SIGINT, frame=None)
    reloader.run()

@pytest.mark.parametrize("should_reload, file", [(True, "example.py"), (False, ".dotted")])
def test_should_reload(tmpdir, should_reload, file):
    update_file = Path(os.path.join(str(tmpdir), file))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = WatchGodReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        update_file.touch()
        time.sleep(0.1)
        assert reloader.should_restart() == should_reload

        reloader.restart()
        reloader.shutdown()
    finally:
        os.chdir(working_dir)
