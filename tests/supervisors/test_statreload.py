import os
import time
from pathlib import Path

from uvicorn.config import Config
from uvicorn.main import Server
from uvicorn.supervisors import StatReload


def wait_for_reload(reloader, until, update_file):
    # I think coverage doesn't fully track this, since it runs in a spawned subprocess.
    while reloader.reload_count < until:  # pragma: nocover
        time.sleep(0.1)
        Path(update_file).touch()


def mock_signal(handle_exit):
    handle_exit(None, None)


def test_statreload(certfile_and_keyfile):
    certfile, keyfile = certfile_and_keyfile
    config = Config(app=None, ssl_certfile=certfile, ssl_keyfile=keyfile)

    server = Server(config)
    type(server).run = lambda self: None

    reloader = StatReload(config)
    reloader.run(server.run)


def test_reload_dirs(tmpdir):
    update_file = os.path.join(str(tmpdir), "example.py")
    config = Config(app=None, reload_dirs=[str(tmpdir)])
    reloader = StatReload(config)
    reloader.run(wait_for_reload, reloader=reloader, until=1, update_file=update_file)


def test_exit_signal(tmpdir):
    config = Config(app=None)
    reloader = StatReload(config)
    reloader.run(mock_signal, handle_exit=reloader.handle_exit)
