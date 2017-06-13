<p align="center">
  <img width="350" height="350" src="https://raw.githubusercontent.com/tomchristie/uvicorn/master/docs/uvicorn.png" alt='uvicorn'>
</p>

<p align="center">
<em>A lightning-fast asyncio server for Python 3.</em>
</p>

---

# Introduction

Uvicorn is intended to be the basis for providing Python 3 with a simple
interface on which to build asyncio web frameworks. It provides the following:

* A lightning-fast asyncio server implementation, using [uvloop][uvloop] and [httptools][httptools].
* A minimal application interface, based on [ASGI][asgi].

## Quickstart

Requirements: Python 3.5.3+

Install using `pip`:

    $ pip install uvicorn

Create an application, in `app.py`:

```python
async def hello_world(message, channels):
    content = b'Hello, world'
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
        'content': content
    }
    await channels['reply'].send(response)
```

Run the server:

```shell
$ uvicorn app:hello_world
```

---

# The messaging interface

Uvicorn introduces a messaging interface broadly based on ASGI...

The application should expose a coroutine callable which takes two arguments:

* `message` is an [ASGI message][asgi-message].  (But see below for ammendments.)
* `channels` is a dictionary of `<unicode string>:<channel interface>`.

The channel interface is an object with the following attributes:

* `.send(message)` - A coroutine for sending outbound messages. Optional.
* `.receive()` - A coroutine for receiving incoming messages. Optional.
* `.name` - A unicode string, uniquely identifying the channel. Optional.

Messages diverge from ASGI in the following ways:

* Messages additionally include a `channel` key, to allow for routing eg. `'channel': 'http.request'`
* Messages do not include channel names, such as `reply_channel` or `body_channel`,
  instead the `channels` dictionary presents the available channels.

---

## Reading the request body

You can stream the request body without blocking the asyncio task pool,
by receiving [request body chunks][request-body-chunk] from the `body` channel.

```python
async def read_body(message, channels):
    """
    Read and return the entire body from an incoming ASGI message.
    """
    body = message.get('body', b'')
    if 'body' in channels:
        while True:
            message_chunk = await channels['body'].receive()
            body += message_chunk['content']
            if not message_chunk.get('more_content', False):
                break
    return body


async def echo_body(message, channels):
    body = await read_body(message, channels)
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
        'content': body
    }
    await channels['reply'].send(response)
```

## Sending streaming responses

You can stream responses by sending [response chunks][response-chunk] to the
`reply` channel:

```python
async def stream_response(message, channels):
    # Send the start of the response.
    await channels['reply'].send({
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
        'content': b'',
        'more_content': True
    })

    # Stream response content.
    for chunk in [b'Hello', b', ', b'world']:
        await channels['reply'].send({
            'content': chunk,
            'more_content': True
        })

    # End the response.
    await channels['reply'].send({
        'content': b'',
        'more_content': False
    })
```

---

# WebSockets

Uvicorn supports websockets, using the same messaging interface described
above, with [ASGI WebSocket messages][websocket-message].

```python
import datetime
import asyncio


async def clock_tick(message, channels):
    if message['channel'] != 'websocket.connect':
        return

    while True:
        text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        channels['reply'].send({'text': text})
        await asyncio.sleep(1)
```

Here's a more complete example that demonstrates a basic WebSocket chat server:

```python
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
    ASGI-style 'Hello, world' application.
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
```

Note that the example above would not currently scale past a single process,
since the set of connected clients is stored in memory. We will be properly
addressing broadcast functionality in the near future.

---

# Adapters

## ASGIAdapter

Provides an ASGI-style interface for an existing WSGI application.

```python
from uvicorn.utils import ASGIAdapter

def app(environ, start_response):
    ...

asgi = ASGIAdapter(app)
```

## WSGIAdapter

Provides a WSGI interface for an existing ASGI-style application.

Useful if you're writing an asyncio application, but want to provide
a backwards-compatibility interface for WSGI.

```python
from uvicorn.utils import WSGIAdapter

async def app(message, channels):
    ...

wsgi = WSGIAdapter(app)
```

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[asgi]: http://channels.readthedocs.io/en/stable/asgi.html
[asgi-message]: http://channels.readthedocs.io/en/stable/asgi/www.html#http-websocket-asgi-message-format-draft-spec
[request-body-chunk]: http://channels.readthedocs.io/en/stable/asgi/www.html#request-body-chunk
[response-chunk]: http://channels.readthedocs.io/en/stable/asgi/www.html#response-chunk
[websocket-message]: http://channels.readthedocs.io/en/latest/asgi/www.html#websocket
