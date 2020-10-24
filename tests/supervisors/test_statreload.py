from tests.supervisors.test_basereload import TestBaseReload
from uvicorn.config import Config
from uvicorn.supervisors.statreload import StatReload


class TestStatReload(TestBaseReload):
    reloader_class = StatReload

    def test_should_reload_when_python_file_is_changed(self):
        file = "example.py"
        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with self.tmpdir.as_cwd():
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert self._reload_tester(reloader, update_file)

            reloader.shutdown()

    def test_should_not_reload_when_javascript_file_is_changed(self):
        file = "example.js"
        update_file = self.tmp_path.joinpath(file)
        update_file.touch()

        with self.tmpdir.as_cwd():
            config = Config(app=None, reload=True)
            reloader = self._setup_reloader(config)

            assert not self._reload_tester(reloader, update_file)

            reloader.shutdown()
