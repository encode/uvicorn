import requests

from uvicorn import Config, Server
from uvicorn.supervisors import Multiprocess


def run(sockets):
    pass


def test_multiprocess_run():
    config = Config(app=None, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.should_exit.set()
    supervisor.run()
