from pathlib import Path
from time import sleep
from typing import Type

import pytest

from tests.utils import as_cwd
from uvicorn.config import Config
from uvicorn.supervisors.basereload import BaseReload, _display_path
from uvicorn.supervisors.statreload import StatReload
from uvicorn.supervisors.watchfilesreload import WatchFilesReload


def run(sockets):
    pass  # pragma: no cover


class TestBaseReload:
    @pytest.fixture(autouse=True)
    def setup(
        self,
        reload_directory_structure: Path,
        reloader_class: Type[BaseReload],
    ):
        self.reload_path = reload_directory_structure
        self.reloader_class = reloader_class

    def _setup_reloader(self, config: Config) -> BaseReload:
        config.reload_delay = 0  # save time
        reloader = self.reloader_class(config, target=run, sockets=[])
        assert config.should_reload
        reloader.startup()
        return reloader

    def _reload_tester(self, touch_soon, reloader: BaseReload, *files: Path) -> bool:
        reloader.restart()

        reloader.restart()
        if isinstance(reloader, StatReload):
            assert not next(reloader)
            sleep(0.1)
            for file in files:
                file.touch()
        else:
            touch_soon(*files)
        return next(reloader)

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchFilesReload])
    def test_reloader_should_initialize(self) -> None:
        """
        A basic sanity check.

        Simply run the reloader against a no-op server, and signal for it to
        quit immediately.
        """
        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)
            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchFilesReload])
    def test_reload_when_python_file_is_changed(self, touch_soon) -> None:
        file = self.reload_path / "main.py"

        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(touch_soon, reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchFilesReload])
    def test_should_reload_when_python_file_in_subdir_is_changed(
        self, touch_soon
    ) -> None:
        file = self.reload_path / "app" / "sub" / "sub.py"

        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(touch_soon, reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchFilesReload])
    def test_should_not_reload_when_python_file_in_excluded_subdir_is_changed(
        self, touch_soon
    ) -> None:
        sub_dir = self.reload_path / "app" / "sub"
        sub_file = sub_dir / "sub.py"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app",
                reload=True,
                reload_excludes=[str(sub_dir)],
            )
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(touch_soon, reloader, sub_file)

            reloader.shutdown()

    @pytest.mark.parametrize(
        "reloader_class, result", [(StatReload, False), (WatchFilesReload, True)]
    )
    def test_reload_when_pattern_matched_file_is_changed(
        self, result: bool, touch_soon
    ) -> None:
        file = self.reload_path / "app" / "js" / "main.js"

        with as_cwd(self.reload_path):
            config = Config(
                app="tests.test_config:asgi_app", reload=True, reload_includes=["*.js"]
            )
            reloader = self._setup_reloader(config)

            assert bool(self._reload_tester(touch_soon, reloader, file)) == result

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchFilesReload])
    def test_should_not_reload_when_exclude_pattern_match_file_is_changed(
        self, touch_soon
    ) -> None:
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

            assert self._reload_tester(touch_soon, reloader, python_file)
            assert self._reload_tester(touch_soon, reloader, css_file)
            assert not self._reload_tester(touch_soon, reloader, js_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchFilesReload])
    def test_should_not_reload_when_dot_file_is_changed(self, touch_soon) -> None:
        file = self.reload_path / ".dotted"

        with as_cwd(self.reload_path):
            config = Config(app="tests.test_config:asgi_app", reload=True)
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(touch_soon, reloader, file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchFilesReload])
    def test_should_reload_when_directories_have_same_prefix(self, touch_soon) -> None:
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

            assert self._reload_tester(touch_soon, reloader, app_file)
            assert self._reload_tester(touch_soon, reloader, app_first_file)

            reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [StatReload, WatchFilesReload])
    def test_should_not_reload_when_only_subdirectory_is_watched(
        self, touch_soon
    ) -> None:
        app_dir = self.reload_path / "app"
        app_dir_file = self.reload_path / "app" / "src" / "main.py"
        root_file = self.reload_path / "main.py"

        config = Config(
            app="tests.test_config:asgi_app",
            reload=True,
            reload_dirs=[str(app_dir)],
        )
        reloader = self._setup_reloader(config)

        assert self._reload_tester(touch_soon, reloader, app_dir_file)
        assert not self._reload_tester(
            touch_soon, reloader, root_file, app_dir / "~ignored"
        )

        reloader.shutdown()

    @pytest.mark.parametrize("reloader_class", [WatchFilesReload])
    def test_override_defaults(self, touch_soon) -> None:
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

            assert self._reload_tester(touch_soon, reloader, dotted_file)
            assert self._reload_tester(touch_soon, reloader, dotted_dir_file)
            assert not self._reload_tester(touch_soon, reloader, python_file)

            reloader.shutdown()


def test_should_watch_one_dir_cwd(mocker, reload_directory_structure):
    mock_watch = mocker.patch("uvicorn.supervisors.watchfilesreload.watch")
    app_dir = reload_directory_structure / "app"
    app_first_dir = reload_directory_structure / "app_first"

    with as_cwd(reload_directory_structure):
        config = Config(
            app="tests.test_config:asgi_app",
            reload=True,
            reload_dirs=[str(app_dir), str(app_first_dir)],
        )
        WatchFilesReload(config, target=run, sockets=[])
        mock_watch.assert_called_once()
        assert mock_watch.call_args[0] == (Path.cwd(),)


def test_should_watch_separate_dirs_outside_cwd(mocker, reload_directory_structure):
    mock_watch = mocker.patch("uvicorn.supervisors.watchfilesreload.watch")
    app_dir = reload_directory_structure / "app"
    app_first_dir = reload_directory_structure / "app_first"
    config = Config(
        app="tests.test_config:asgi_app",
        reload=True,
        reload_dirs=[str(app_dir), str(app_first_dir)],
    )
    WatchFilesReload(config, target=run, sockets=[])
    mock_watch.assert_called_once()
    assert set(mock_watch.call_args[0]) == {
        app_dir,
        app_first_dir,
        Path.cwd(),
    }


def test_display_path_relative(tmp_path):
    with as_cwd(tmp_path):
        p = tmp_path / "app" / "foobar.py"
        assert _display_path(p) == "'app/foobar.py'"


def test_display_path_non_relative():
    p = Path("/foo/bar.py")
    assert _display_path(p) == "'/foo/bar.py'"
