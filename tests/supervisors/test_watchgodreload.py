from tests.supervisors.test_basereload import TestBaseReload
from uvicorn.config import Config
from uvicorn.supervisors.watchgodreload import WatchGodReload


class TestWatchGodReload(TestBaseReload):
    reloader_class = WatchGodReload

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
