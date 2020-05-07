import asyncio
import random


async def app(scope, receive, send):
    assert scope['type'] == 'http'

    await send({
        'type': 'http.response.start',
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
    })
    wait4 = random.uniform(1,5)
    await asyncio.sleep(wait4)
    helloworld = f"hello world I slept {str(wait4)}".encode()
    await send({
        'type': 'http.response.body',
        'body': helloworld,
    })
