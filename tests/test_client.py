import asyncio

import requests

from tests.client import TestClient


async def hello_world(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send(
        {"type": "http.response.body", "body": b"hello, world", "more_body": False}
    )


def test_explicit_base_url():
    client = TestClient(hello_world, base_url="http://testserver:321")
    response = client.get("/")
    assert response.status_code == 200
    assert response.text == "hello, world"


def test_explicit_host():
    client = TestClient(hello_world)
    response = client.get("/", headers={"host": "example.org"})
    assert response.status_code == 200
    assert response.text == "hello, world"


async def wait_for_disconnect(receive):
    while True:
        print('h')
        p = await receive()
        if p['type'] == 'http.disconnect':
            print('Disconnected!')
            break


async def hang(scope, receive, send):
    await asyncio.sleep(0.2)
    m = await receive()

    if m['type'] == 'lifespan.startup':
        await send({'type': 'lifespan.startup.complete'})
    elif m['type'] == 'http.request':
        if scope['path'] == '/foo':
            print('foo')
            asyncio.create_task(wait_for_disconnect(receive))
            await asyncio.sleep(0.2)
        await send({'type': 'http.response.start', 'status': 404})
        await send({'type': 'http.response.body', 'body': b'Not found!\n'})


def test_concurrent_requests() -> None:
    with TestClient(hang) as client:
        client.get("/foo")
        client.get("/bar")
