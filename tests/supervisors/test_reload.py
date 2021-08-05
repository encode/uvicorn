import signal
from pathlib import Path
from time import sleep

import pytest

from tests.utils import as_cwd
from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload
from uvicorn.supervisors.statreload import StatReload
from uvicorn.supervisors.watchgodreload import WatchGodReload


class TestBaseReload:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, reloader_class: BaseReload):
        self.tmp_path = tmp_path
        self.reloader_class = reloader_class

    def run(self, sockets):
        pass  # pragma: no cover

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

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_reloader_should_initialize(self) -> None:
        """
        A basic sanity check.

        Simply run the reloader against a no-op server, and signal for it to
        quit immediately.
        """
        config = Config(app=None, reload=True)
        reloader = self._setup_reloader(config)
        reloader.shutdown()

    @pytest.mark.parametrize(
        "reloader_class, result", [(StatReload, True), (WatchGodReload, True)]
    )
    def test_reload_when_python_file_is_changed(self, result: bool) -> None:
        file = "example.py"
        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, update_file) == result

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_reload_when_python_file_in_subdir_is_changed(self) -> None:
        file = "example.py"
        sub_dir = self.tmp_path.joinpath("app", "subdir")
        update_file = sub_dir.joinpath(file)
        sub_dir.mkdir(parents=True)
        update_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, update_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchGodReload])
    def test_should_not_reload_when_python_file_in_subdir_is_changed(self) -> None:
        file = "example.py"
        sub_dir = self.tmp_path.joinpath("app", "subdir")
        update_file = sub_dir.joinpath(file)
        sub_dir.mkdir(parents=True)
        update_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(
                app=None,
                reload=True,
                reload_excludes=[str(sub_dir)],
            )
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, update_file)

            reloader.shutdown()

    @pytest.mark.parametrize(
        "reloader_class, result", [(StatReload, False), (WatchGodReload, True)]
    )
    def test_reload_when_javascript_file_is_changed(self, result: bool) -> None:
        file = "example.js"
        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(app=None, reload=True, reload_includes=["*.js"])
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, update_file) == result

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class, result", [(WatchGodReload, False)])
    def test_should_not_reload_when_javascript_file_is_changed(
        self, result: bool
    ) -> None:
        file = "example.js"

        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(
                app=None, reload=True, reload_includes=["*"], reload_excludes=["*.js"]
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, update_file) == result

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_not_reload_when_dot_file_is_changed(self) -> None:
        file = ".dotted"

        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, update_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_reload_when_directories_have_same_prefix(self) -> None:
        file = "example.py"

        app_dir = self.tmp_path.joinpath("app")
        app_ext_dir = self.tmp_path.joinpath("app_extension")
        app_file = app_dir.joinpath(file)
        app_ext_file = app_ext_dir.joinpath(file)
        app_dir.mkdir()
        app_ext_dir.mkdir()
        app_file.touch()
        app_ext_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(
                app=None, reload=True, reload_dirs=[str(app_dir), str(app_ext_dir)]
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, app_file)
            assert self._reload_tester(reloader, app_ext_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_parse_dir_from_includes(self) -> None:
        file = "example.py"

        app_dir = self.tmp_path.joinpath("app")
        app_ext_dir = self.tmp_path.joinpath("app_extension")
        app_file = app_dir.joinpath(file)
        app_ext_file = app_ext_dir.joinpath(file)
        app_dir.mkdir()
        app_ext_dir.mkdir()
        app_file.touch()
        app_ext_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(app=None, reload=True, reload_includes=[str(app_dir)])
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, app_file)
            assert not self._reload_tester(reloader, app_ext_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload])
    def test_should_not_parse_filetype_from_includes(self) -> None:
        file = "example.js"
        app_dir = self.tmp_path.joinpath("app")
        app_file = app_dir.joinpath(file)
        app_dir.mkdir()
        app_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(app=None, reload=True, reload_includes=["*.js"])
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, app_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchGodReload])
    def test_override_defaults(self) -> None:
        dotted = ".dotted"
        python = "example.py"

        dotted_file = self.tmp_path.joinpath(dotted)
        python_file = self.tmp_path.joinpath(python)
        dotted_file.touch()
        python_file.touch()

        with as_cwd(self.tmp_path):
            config = Config(
                app=None, reload=True, reload_includes=[".*"], reload_excludes=["*.py"]
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, dotted_file)
            assert not self._reload_tester(reloader, python_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload])
    def test_should_print_full_path_for_non_relative(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        file = "example.py"
        app_dir = self.tmp_path / "app"
        ext_dir = self.tmp_path.joinpath("ext")
        ext_file = ext_dir.joinpath(file)

        app_dir.mkdir()
        ext_dir.mkdir()
        ext_file.touch()

        with as_cwd(app_dir):
            config = Config(app=None, reload=True, reload_dirs=[str(ext_dir)])
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, ext_file)

            assert (
                caplog.records[-1].message
                == f"StatReload detected file change in '{str(ext_file)}'. Reloading..."
            )

            reloader.shutdown()
