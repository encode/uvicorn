from uvicorn import Config, Server
from uvicorn.supervisors import Multiprocess
import requests


def run(sockets):
    pass


async def app(scope, receive, send):
    assert scope['type'] == 'http'
    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ]
    })
    await send({
        'type': 'http.response.body',
        'body': b'Hello, world!',
    })


def test_multiprocess_run():
    config = Config(app=None, workers=2)
    supervisor = Multiprocess(config, target=run, sockets=[])
    supervisor.should_exit.set()
    supervisor.run()


def test_multiprocess_request():
    config = Config(app=app, workers=2)
    server = Server(config=config)
    supervisor = Multiprocess(config, target=server.run, sockets=[])
    supervisor.startup()
    #response = requests.get("http://127.0.0.1:8000")
    #assert response.status_code == 200
    #assert response.text == 'Hello, world!'
    supervisor.shutdown()
