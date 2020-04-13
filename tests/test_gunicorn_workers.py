import platform
import sys
import time
from multiprocessing.context import Process

import pytest
import requests

gunicorn_app_base = pytest.importorskip("gunicorn.app.base")


async def handler_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"Hello", "more_body": False})


class StandaloneApplication(gunicorn_app_base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {
            key: value
            for key, value in self.options.items()
            if key in self.cfg.settings and value is not None
        }
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


@pytest.mark.skipif(
    sys.platform.startswith("win") or platform.python_implementation() == "PyPy",
    reason="Skipping uds test on Windows and PyPy",
)
def test_gunicorn_uvicorn():

    options = {
        "bind": "%s:%s" % ("127.0.0.1", "8000"),
        "workers": 1,
        "worker_class": "uvicorn.workers.UvicornWorker",
        "log_level": "debug",
    }
    gunicorn_uvicorn_server = StandaloneApplication(handler_app, options)
    process = Process(target=gunicorn_uvicorn_server.run)
    process.start()
    time.sleep(0.1)
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 200
    assert response.content == b"Hello"
    process.terminate()
    # needed timeout for travis or the port wont get released fast enough
    # and will "block" subsequent tests
    time.sleep(1)
