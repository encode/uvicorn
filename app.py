def hello_world(message):
    content = b"Hello, world!\n"
    return message['reply_channel'].send({
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
            [b'content-length', str(len(content)).encode('ascii')],
        ],
        'content': content
    })
