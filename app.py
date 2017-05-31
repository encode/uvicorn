import asyncio


def hello_world(message):
    content = b'<html><h1>Hello, world</h1></html>'
    reply_channel = message['reply_channel']
    reply_channel.send({
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
            [b'content-length', str(len(content)).encode('ascii')]
        ],
        'content': content
    })


def async_hello_world(message):
    loop = message['channel_layer'].loop
    loop.create_task(_async_hello_world(message))


async def _async_hello_world(message):
    await asyncio.sleep(1)
    content = b'<html><h1>Hello, world</h1></html>'
    reply_channel = message['reply_channel']
    reply_channel.send({
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
            [b'content-length', str(len(content)).encode('ascii')]
        ],
        'content': content
    })
