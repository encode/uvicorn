import asyncio
import functools
import threading
import requests
import pytest
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


def test_invalid_upgrade():
    async def app(message, channels):
        pass

    with run_server(app) as url:
        url = url.replace('ws://', 'http://')
        response = requests.get(url, headers={'upgrade': 'websocket', 'connection': 'upgrade'})
        assert response.status_code == 400


def test_accept_connection():
    async def app(message, channels):
        await channels['reply'].send({'accept': True})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.open

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        is_open = loop.run_until_complete(open_connection(url))
        assert is_open
        loop.close()


def test_reject_connection():
    async def app(message, channels):
        await channels['reply'].send({'accept': False})

    async def open_connection(url):
        async with websockets.connect(url) as websocket:
            return websocket.state_name

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        with pytest.raises(websockets.exceptions.InvalidHandshake):
            state = loop.run_until_complete(open_connection(url))
        loop.close()


def test_send_text_data_to_client():
    async def app(message, channels):
        if message['channel'] == 'websocket.connect':
            await channels['reply'].send({'text': '123'})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(get_data(url))
        assert data == '123'
        loop.close()


def test_send_binary_data_to_client():
    async def app(message, channels):
        if message['channel'] == 'websocket.connect':
            await channels['reply'].send({'bytes': b'123'})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            return await websocket.recv()

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(get_data(url))
        assert data == b'123'
        loop.close()


def test_send_and_close_connection():
    async def app(message, channels):
        if message['channel'] == 'websocket.connect':
            await channels['reply'].send({'text': '123', 'close': True})

    async def get_data(url):
        async with websockets.connect(url) as websocket:
            data = await websocket.recv()
            try:
                await websocket.recv()
                is_open = True
            except:
                is_open = False
            return (data, is_open)

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        (data, is_open) = loop.run_until_complete(get_data(url))
        assert data == '123'
        assert not is_open
        loop.close()


def test_send_text_data_to_server():
    async def app(message, channels):
        if message['channel'] == 'websocket.connect':
            await channels['reply'].send({'accept': True})
        elif message['channel'] == 'websocket.receive':
            data = message.get('text')
            await channels['reply'].send({'text': data})

    async def send_text(url):
        async with websockets.connect(url) as websocket:
            await websocket.send('abc')
            return await websocket.recv()

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(send_text(url))
        assert data == 'abc'
        loop.close()


def test_send_binary_data_to_server():
    async def app(message, channels):
        if message['channel'] == 'websocket.connect':
            await channels['reply'].send({'accept': True})
        elif message['channel'] == 'websocket.receive':
            data = message.get('bytes')
            await channels['reply'].send({'bytes': data})

    async def send_text(url):
        async with websockets.connect(url) as websocket:
            await websocket.send(b'abc')
            return await websocket.recv()

    with run_server(app) as url:
        loop = asyncio.new_event_loop()
        data = loop.run_until_complete(send_text(url))
        assert data == b'abc'
        loop.close()
