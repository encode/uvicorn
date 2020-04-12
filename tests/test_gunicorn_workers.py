import time
from multiprocessing.context import Process

import gunicorn.app.base
import requests



async def handler_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"Hello", "more_body": False})


class StandaloneApplication(gunicorn.app.base.BaseApplication):

    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application


def test_gunicorn_uvicorn():
    options = {
        'bind': '%s:%s' % ('127.0.0.1', '8080'),
        'workers': 1,
        "worker_class": "uvicorn.workers.UvicornWorker"
        
    }
    gunicorn_uvicorn_server = StandaloneApplication(handler_app, options)
    process = Process(target=gunicorn_uvicorn_server.run)
    process.start()
    time.sleep(1)
    response = requests.get("http://127.0.0.1:8080")
    assert response.status_code == 200
    assert response.content == b"Hello"
    # need a timeout or it wont close
    process.join(timeout=2)
    print("here")
