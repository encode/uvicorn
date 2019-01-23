from uvicorn.main import Server
from uvicorn.config import Config
import requests
import threading


def test_run():
    class App:
        def __init__(self, scope):
            if scope['type'] != 'http':
                raise Exception()

        async def __call__(self, receive, send):
            await send({"type": "http.response.start", "status": 204, "headers": []})
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    class CustomServer(Server):
        def install_signal_handlers(self):
            pass

    config = Config(
        app=App,
        loop="asyncio",
        limit_max_requests=1
    )
    server = CustomServer(config=config)

    thread = threading.Thread(target=server.run)
    thread.start()
    server.started.wait()
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()
