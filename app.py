async def read_body(channels):
    body = b''
    if 'body' in channels:
        while True:
            message_chunk = await channels['body'].recieve()
            body += message_chunk['content']
            if not message_chunk['more_content']:
                break
    return body


async def hello_world(message, channels):
    body = await read_body(channels)
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
        ],
        'content': b'<html><h1>Hello, world</h1></html>'
    }
    await channels['reply'].send(response)
