from uvicorn.config import Config
from uvicorn.reloaders.statreload import StatReload


def no_op():
    pass


def test_statreload():
    config = Config(app=None)
    reloader = StatReload(config)
    reloader.run(no_op)
