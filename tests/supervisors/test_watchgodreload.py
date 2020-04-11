import os
import signal
import time
from pathlib import Path

from uvicorn.config import Config
from uvicorn.supervisors.watchgodreload import WatchGodReload


def run(sockets):
    pass


def test_statreload(certfile_and_keyfile):
    config = Config(app=None)
    reloader = WatchGodReload(config, target=run, sockets=[])
    reloader.run()


def test_should_reload(tmpdir, caplog):
    update_file = Path(os.path.join(str(tmpdir), "example.py"))
    update_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(app=None, reload=True)
        reloader = WatchGodReload(config, target=run, sockets=[])
        reloader.run()

        update_file.touch()
        time.sleep(0.1)

        assert "toto" in caplog

    finally:
        os.chdir(working_dir)
