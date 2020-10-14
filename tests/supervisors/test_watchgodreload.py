import os
import signal
import time
from pathlib import Path

from uvicorn.config import Config
from uvicorn.supervisors.watchgodreload import WatchGodReload


def run(sockets):
    pass


def test_watchgodreload(
    tls_ca_certificate_pem_path, tls_ca_certificate_private_key_path
):
    config = Config(app=None)
    reloader = WatchGodReload(config, target=run, sockets=[])
    reloader.signal_handler(sig=signal.SIGINT, frame=None)
    reloader.run()


def test_should_reload_when_python_file_is_changed(tmpdir):
    file = "example.py"
    update_file = Path(tmpdir).joinpath(file)
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


def test_should_not_reload_when_dot_file_is_changed(tmpdir):
    file = ".dotted"
    update_file = Path(tmpdir).joinpath(file)
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


def test_should_reload_when_directories_have_same_prefix(tmpdir):
    file = "example.py"
    tmpdir_path = Path(tmpdir)
    app_dir = tmpdir_path.joinpath("app")
    app_ext_dir = tmpdir_path.joinpath("app_extension")
    app_file = app_dir.joinpath(file)
    app_ext_file = app_ext_dir.joinpath(file)
    app_dir.mkdir()
    app_ext_dir.mkdir()
    app_file.touch()
    app_ext_file.touch()

    working_dir = os.getcwd()
    os.chdir(str(tmpdir))
    try:
        config = Config(
            app=None, reload=True, reload_dirs=[str(app_dir), str(app_ext_dir)]
        )
        reloader = WatchGodReload(config, target=run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()

        assert not reloader.should_restart()
        time.sleep(0.1)
        app_file.touch()
        assert reloader.should_restart()

        reloader.restart()

        assert not reloader.should_restart()
        time.sleep(0.1)
        app_ext_file.touch()
        assert reloader.should_restart()

        reloader.shutdown()
    finally:
        os.chdir(working_dir)
