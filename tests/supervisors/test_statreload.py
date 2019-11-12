from uvicorn.config import Config
from uvicorn.supervisors import StatReload


def run(sockets):
    pass


def test_statreload():
    config = Config(app=None, reload=True)
    reloader = StatReload(config, target=run, sockets=[])
    reloader.should_exit.set()
    reloader.run()
