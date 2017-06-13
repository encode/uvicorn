from uvicorn.utils import ASGIAdapter, WSGIAdapter


# Run: `uvicorn app:asgi`
async def asgi(message, channels):
    """
    ASGI-style 'Hello, world' application.
    """
    await channels['reply'].send({
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
        'content': b'Hello, world\n'
    })


# Run: `gunicorn app:wsgi`
def wsgi(environ, start_response):
    """
    WSGI 'Hello, world' application.
    """
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    return [b'Hello, world\n']


# Run: `uvicorn app:asgi_from_wsgi`
asgi_from_wsgi = ASGIAdapter(wsgi)


# Run: `gunicorn app:wsgi_from_asgi`
wsgi_from_asgi = WSGIAdapter(asgi)


# Run: `uvicorn app:chat_server`
index_html = b"""
<!DOCTYPE html>
<html>
    <head>
        <title>WebSocket demo</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://127.0.0.1:8000/");

            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };

            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


clients = set()


async def chat_server(message, channels):
    """
    A WebSocket based chat server.
    """
    if message['channel'] == 'websocket.connect':
        clients.add(channels['reply'])

    elif message['channel'] == 'websocket.receive':
        for client in clients:
            await client.send({'text': message['text']})

    elif message['channel'] == 'websocket.disconnect':
        clients.remove(channels['reply'])

    elif message['channel'] == 'http.request':
        await channels['reply'].send({
            'status': 200,
            'headers': [
                [b'content-type', b'text/html'],
            ],
            'content': index_html
        })
