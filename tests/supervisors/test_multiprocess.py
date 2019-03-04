from uvicorn.config import Config
from uvicorn.supervisors import Multiprocess


def no_op():
    pass


def mock_signal(handle_exit):
    handle_exit(None, None)


def test_multiprocess():
    config = Config(app=None, workers=2)
    reloader = Multiprocess(config)
    reloader.run(no_op)


def test_exit_signal():
    config = Config(app=None, workers=2)
    reloader = Multiprocess(config)
    reloader.run(mock_signal, handle_exit=reloader.handle_exit)
