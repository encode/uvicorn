async def app(message, channels):
    content = b'Hello, world'
    await channels['reply'].send({
        'status': 200,
        'headers': [
            [b'content-length', str(len(content)).encode()]
        ],
        'content': content
    })
