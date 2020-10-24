import signal
from pathlib import Path
from time import sleep

import pytest

from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload


class TestBaseReload:
    reloader_class = BaseReload
    tmp_path: Path

    @pytest.fixture(autouse=True)
    def setup(self, tmpdir):
        self.tmpdir = tmpdir
        self.tmp_path = Path(tmpdir)

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
