<p align="center">
  <img width="320" height="320" src="https://raw.githubusercontent.com/tomchristie/uvicorn/master/docs/uvicorn.png" alt='uvicorn'>
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

We'll start with an example that simply echos any incoming websocket messages
back to the client.

```python
async def echo(message, channels):
    if message['channel'] == 'websocket.receive':
        text = message['text']
        await channels['reply'].send({
            'text': text
        })
```

Another example, this time demonstrating a websocket connection that sends
back the current time to each connected client, roughly once per second.

```python
import datetime
import asyncio


async def send_times(channel):
    while True:
        text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await channel.send({'text': text})
        await asyncio.sleep(1)


async def tick(message, channels):
    if message['channel'] == 'websocket.connect':
        loop = asyncio.get_event_loop()
        loop.create_task(send_times(channels['reply']))
```

Here's a more complete example that demonstrates a basic WebSocket chat server:

**index.html**:

```html
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
```

**app.py**:

```python
clients = set()
with open('index.html', 'rb') as file:
    homepage = file.read()

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
            'content': homepage
        })
```

Note that the example above will only work properly when running as a single
process on a single machine, since the set of connected clients is stored in
memory.

In order to build properly scalable WebSocket services you'll typically want
some way of sending messages across a group of client connections, each of
which may be connected to a different server instance...

---

# Broadcast

Uvicorn includes broadcast functionality, using Redis Pub/Sub.

First, make sure to install the `asyncio_redis` package:

```shell
$ pip install asyncio_redis
```

Broadcast functionality is not integrated directly into the server, but is
included as application-level middleware. You can install the broadcast module
by wrapping it around your existing application, like so:

```python
from uvicorn.broadcast import BroadCastMiddleware

async def my_app(messages, channels):
    ...

app = BroadCastMiddleware(my_app, 'localhost', 6379)
```

This will make a `groups` channel available, which accepts the following
messages:

#### Add

```python
await channels['groups'].send({
    'group': <name>,
    'add': <channel_name>
})
```

Add a channel to the given group.

#### Discard

```python
await channels['groups'].send({
    'group': <name>,
    'discard': <channel_name>
})
```

Remove a channel from the given group.

#### Send

```python
await channels['groups'].send({
    'group': <name>,
    'send': <message>
})
```

Send a message to all channels in the given group.

## Example

Let's add broadcast functionality to our previous chat server example...

```python
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


chat_server = BroadcastMiddleware(chat_server)
```

We can now start up a connected group of chat server instances:

First, start a Redis server:

```shell
$ redis-server
```

Then start one or more Uvicorn instances:

```shell
$ uvicorn app:chat_server --bind 127.0.0.1:8000
$ uvicorn app:chat_server --bind 127.0.0.1:8001
$ uvicorn app:chat_server --bind 127.0.0.1:8002
```

You can now open multiple browser windows, each connected to a different
server instance, and send chat messages between them.

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
