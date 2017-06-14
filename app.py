"""
Start a redis server:

$ redis-server

Start one or more uvicorn instances:

$ uvicorn app:chat_server --bind 127.0.0.1:8000
$ uvicorn app:chat_server --bind 127.0.0.1:8001
$ uvicorn app:chat_server --bind 127.0.0.1:8002
"""
from uvicorn.broadcast import BroadcastMiddleware


with open('index.html', 'rb') as file:
    homepage = file.read()


async def chat_server(message, channels):
    """
    A WebSocket based chat server.
    """
    if message['channel'] == 'websocket.connect':
        await channels['groups'].send({
            'group': 'chat',
            'add': channels['reply'].name
        })

    elif message['channel'] == 'websocket.receive':
        await channels['groups'].send({
            'group': 'chat',
            'send': {'text': message['text']}
        })

    elif message['channel'] == 'websocket.disconnect':
        await channels['groups'].send({
            'group': 'chat',
            'discard': channels['reply'].name
        })

    elif message['channel'] == 'http.request':
        await channels['reply'].send({
            'status': 200,
            'headers': [
                [b'content-type', b'text/html'],
            ],
            'content': homepage
        })


chat_server = BroadcastMiddleware(chat_server, 'localhost', 6379)
