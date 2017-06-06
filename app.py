def hello_world(message):
    content = b'<html><h1>Hello, world</h1></html>'
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
        ],
        'content': content
    }
    message['reply_channel'].send(response)
