import asyncio
import functools
import threading
import requests
import websockets
from contextlib import contextmanager
from uvicorn.protocols import http


def run_loop(loop):
    loop.run_forever()
    loop.close()


@contextmanager
def run_server(app):
    asyncio.set_event_loop(None)
    loop = asyncio.new_event_loop()
    protocol = functools.partial(http.HttpProtocol, consumer=app, loop=loop)
    create_server_task = loop.create_server(protocol, host='127.0.0.1')
    server = loop.run_until_complete(create_server_task)
    url = 'ws://127.0.0.1:%d/' % server.sockets[0].getsockname()[1]
    try:
        # Run the event loop in a new thread.
        threading.Thread(target=run_loop, args=[loop]).start()
        # Return the contextmanager state.
        yield url
    finally:
        # Close the loop from our main thread.
        loop.call_soon_threadsafe(loop.stop)


async def app(message, channels):
    pass


def test_invalid_upgrade():
    with run_server(app) as url:
        url = url.replace('ws://', 'http://')
        response = requests.get(url, headers={'upgrade': 'websocket', 'connection': 'upgrade'})
        assert response.status_code == 400


def test_open_connection():
    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.state_name

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(open_connection(url))
        assert state == 'OPEN'
        loop.close()
