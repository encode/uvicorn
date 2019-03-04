from uvicorn.config import Config
from uvicorn.supervisors import Multiprocess


def no_op():
    pass


def mock_signal(reloader):
    reloader.handle_exit(None, None)


def test_multiprocess():
    config = Config(app=None, workers=2)
    reloader = Multiprocess(config)
    reloader.run(no_op)


def test_exit_signal():
    config = Config(app=None, workers=2)
    reloader = Multiprocess(config)
    reloader.run(mock_signal, reloader=reloader)
