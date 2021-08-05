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
    def setup(
        self,
        reload_directory_structure: Path,
        reloader_class: BaseReload,
    ):
        self.reload_path = reload_directory_structure
        self.reloader_class = reloader_class

    def run(self, sockets):
        pass  # pragma: no cover

    def _setup_reloader(self, config: Config) -> BaseReload:
        reloader = self.reloader_class(config, target=self.run, sockets=[])
        assert config.should_reload
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
        config = Config(app="tests.test_config:asgi_app", reload=True)
        reloader = self._setup_reloader(config)
        reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_reload_when_python_file_is_changed(self) -> None:
        file = self.reload_path / "main.py"

        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_reload_when_python_file_in_subdir_is_changed(self) -> None:
        file = self.reload_path / "app" / "sub" / "sub.py"

        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchGodReload])
    def test_should_not_reload_when_python_file_in_subdir_is_changed(self) -> None:
        sub_dir = self.reload_path / "app" / "sub"
        sub_file = sub_dir / "sub.py"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_excludes=[str(sub_dir)],
            )
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, sub_file)

            reloader.shutdown()

    @pytest.mark.parametrize(
        "reloader_class, result", [(StatReload, False), (WatchGodReload, True)]
    )
    def test_reload_when_pattern_matched_file_is_changed(self, result: bool) -> None:
        file = self.reload_path / "app" / "js" / "main.js"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app", reload=True, reload_includes=["*.js"]
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, file) == result

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchGodReload])
    def test_should_not_reload_when_exclude_pattern_match_file_is_changed(self) -> None:
        python_file = self.reload_path / "app" / "src" / "main.py"
        css_file = self.reload_path / "app" / "css" / "main.css"
        js_file = self.reload_path / "app" / "js" / "main.js"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_includes=["*"],
                reload_excludes=["*.js"],
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, python_file)
            assert self._reload_tester(reloader, css_file)
            assert not self._reload_tester(reloader, js_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_not_reload_when_dot_file_is_changed(self) -> None:
        file = self.reload_path / ".dotted"

        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_reload_when_directories_have_same_prefix(self) -> None:
        app_dir = self.reload_path / "app"
        app_file = app_dir / "src" / "main.py"
        app_first_dir = self.reload_path / "app_first"
        app_first_file = app_first_dir / "src" / "main.py"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_dirs=[str(app_dir), str(app_first_dir)],
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, app_file)
            assert self._reload_tester(reloader, app_first_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchGodReload])
    def test_should_parse_dir_from_includes(self) -> None:
        app_dir = self.reload_path / "app"
        app_file = app_dir / "src" / "main.py"
        app_first_dir = self.reload_path / "app_first"
        app_first_file = app_first_dir / "src" / "main.py"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_includes=[str(app_dir)],
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, app_file)
            assert not self._reload_tester(reloader, app_first_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload])
    def test_should_not_parse_filetype_from_includes(self) -> None:
        file = self.reload_path / "app" / "js" / "main.js"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app", reload=True, reload_includes=["*.js"]
            )
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchGodReload])
    def test_override_defaults(self) -> None:
        dotted_file = self.reload_path / ".dotted"
        dotted_dir_file = self.reload_path / ".dotted_dir" / "file.txt"
        python_file = self.reload_path / "main.py"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                # We need to add *.txt otherwise no regular files will match
                reload_includes=[".*", "*.txt"],
                reload_excludes=["*.py"],
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, dotted_file)
            assert self._reload_tester(reloader, dotted_dir_file)
            assert not self._reload_tester(reloader, python_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload])
    def test_should_print_full_path_for_non_relative(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        app_dir = self.reload_path / "app"
        app_first_dir = self.reload_path / "app_first"
        app_first_file = app_first_dir / "src" / "main.py"

        with as_cwd(app_dir):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_dirs=[str(app_first_dir)],
            )
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, app_first_file)

            assert (
                caplog.records[-1].message
                == f"StatReload detected file change in '{str(app_first_file)}'."
                " Reloading..."
            )

            reloader.shutdown()
