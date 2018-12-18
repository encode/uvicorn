from uvicorn import run
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

    is_ready = threading.Event()
    thread = threading.Thread(
        target=run,
        kwargs={
            "app": App,
            "loop": "asyncio",
            "install_signal_handlers": False,
            "ready_event": is_ready,
            "limit_max_requests": 1,
        },
    )
    thread.start()
    is_ready.wait()
    response = requests.get("http://127.0.0.1:8000")
    assert response.status_code == 204
    thread.join()
