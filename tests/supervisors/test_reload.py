import signal
from pathlib import Path
from time import sleep

import pytest

from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload
from uvicorn.supervisors.statreload import StatReload
from uvicorn.supervisors.watchgodreload import WatchGodReload


@pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
class TestBaseReload:
    tmp_path: Path

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir, reloader_class):
        self.tmpdir = tmpdir
        self.tmp_path = Path(tmpdir)
        self.reloader_class = reloader_class

    def run(self, sockets):
        pass

    def _setup_reloader(self, config: Config) -> BaseReload:
        reloader = self.reloader_class(config, target=self.run, sockets=[])
        reloader.signal_handler(sig=signal.SIGINT, frame=None)
        reloader.startup()
        return reloader

    def _reload_tester(self, reloader: BaseReload, file: Path) -> bool:
        reloader.restart()
        assert not reloader.should_restart()
        sleep(0.1)
        file.touch()
        return reloader.should_restart()

    def test_reloader_should_initialize(self):
        """
        A basic sanity check.

        Simply run the reloader against a no-op server, and signal for it to
        quit immediately.
        """
        config = Config(app=None, reload=True)
        reloader = self._setup_reloader(config)
        reloader.shutdown()

    def test_should_reload_when_python_file_is_changed(self):
        file = "example.py"
        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with self.tmpdir.as_cwd():
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, update_file)

            reloader.shutdown()

    def test_should_not_reload_when_dot_file_is_changed(self):
        file = ".dotted"

        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with self.tmpdir.as_cwd():
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, update_file)

            reloader.shutdown()

    def test_should_reload_when_directories_have_same_prefix(self):
        file = "example.py"

        app_dir = self.tmp_path.joinpath("app")
        app_ext_dir = self.tmp_path.joinpath("app_extension")
        app_file = app_dir.joinpath(file)
        app_ext_file = app_ext_dir.joinpath(file)
        app_dir.mkdir()
        app_ext_dir.mkdir()
        app_file.touch()
        app_ext_file.touch()

        with self.tmpdir.as_cwd():
            config = Config(
                app=None, reload=True, reload_dirs=[str(app_dir), str(app_ext_dir)]
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, app_file)
            assert self._reload_tester(reloader, app_ext_file)

            reloader.shutdown()
