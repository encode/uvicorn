# Introduction

Python currently lacks a minimal low-level server/application interface for
asyncio frameworks. Filling this gap means we'd be able to start building
a common set of tooling usable across all asyncio frameworks.

Uvicorn is an attempt to resolve this, by providing:

* A lightning-fast asyncio server implementation, using [uvloop][uvloop] and [httptools][httptools].
* A minimal application interface, based on [ASGI][asgi].

It currently supports HTTP, WebSockets, Pub/Sub broadcast, and is open
to extension to other protocols & messaging styles.

## Quickstart

Requirements: Python 3.5.3+

Install using `pip`:

```shell
$ pip install uvicorn
```

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

# Messaging interface

Uvicorn introduces a messaging interface broadly based on [ASGI][asgi]...

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

## Example

An incoming HTTP request might be represented with the following `message`
and `channels` information:

**message**:

```python
{
    'channel': 'http.request',
    'scheme': 'http',
    'root_path': '',
    'server': ('127.0.0.1', 8000),
    'http_version': '1.1',
    'method': 'GET',
    'path': '/',
    'headers': [
        [b'host', b'127.0.0.1:8000'],
        [b'user-agent', b'curl/7.51.0'],
        [b'accept', b'*/*']
    ]
}
```

**channels**:

```python
{
    'reply': <ReplyChannel>
}
```

In order to respond, the application would `send()` an HTTP response to
the reply channel, for instance:

```python
await channels['reply'].send({
    'status': 200,
    'headers': [
        [b'content-type', b'text/plain'],
    ],
    'content': b'Hello, world'
})
```

# HTTP

The format for HTTP request and response messages is described in [the ASGI documentation][http-message].

## Requests & responses

Here's an example that displays the method and path used in the incoming request:

```python
async def echo_method_and_path(message, channels):
    body = 'Received %s request to %s' % (message['method'], message['path'])
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/plain'],
        ],
        'content': body.encode('utf-8')
    }
    await channels['reply'].send(response)
```

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

## Streaming responses

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

# WebSockets

Uvicorn supports websockets, using the same messaging interface described
above, with [ASGI WebSocket messages][websocket-message].

## Accepting connections

The first thing you need to handle with an incoming websocket connection
is determining if you want the server to accept or reject the connection.

The initial connect message will include all the regular HTTP header and URL
information, which will allow you to route and authenticate any incoming
connections.

```python
async def echo(message, channels):
    if message['channel'] == 'websocket.connect':
        await channels['reply'].send({'accept': True})
```

A connection can be terminated either by sending `'accept': False` as the
initial reply message, or by sending `'close': True` to an already established
connection.

## Incoming & outgoing data

Now that we're able to establish an incoming connection, we'll want to actually
do something with it.

We'll start with an example that simply echos any incoming websocket messages
back to the client.

```python
async def echo(message, channels):
    if message['channel'] == 'websocket.connect':
        await channels['reply'].send({'accept': True})
    elif message['channel'] == 'websocket.receive':
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


async def tick(message, channels):
    if message['channel'] == 'websocket.connect':
        await channels['reply'].send({'accept': True})
        while True:
            text = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await channels['reply'].send({'text': text})
            await asyncio.sleep(1)
```

## Connects & disconnects

Connect and disconnect messages allow you to keep track of connected clients.

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
        await channels['reply'].send({'accept': True})
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

# Broadcast

Uvicorn includes broadcast functionality, using Redis Pub/Sub.

First, make sure to install the `uvitools` package:

```shell
$ pip install uvitools
```

Broadcast functionality is not integrated directly into the server, but is
included as application-level middleware. You can install the broadcast module
by wrapping it around your existing application, like so:

```python
from uvitools.broadcast import BroadCastMiddleware

async def my_app(messages, channels):
    ...

app = BroadCastMiddleware(my_app, 'localhost', 6379)
```

## Commands

Including the broadcast middleware will make a `groups` channel available,
which accepts the following command messages:

### Add

```python
await channels['groups'].send({
    'group': <name>,
    'add': <channel_name>
})
```

Add a channel to the given group.

### Discard

```python
await channels['groups'].send({
    'group': <name>,
    'discard': <channel_name>
})
```

Remove a channel from the given group.

### Send

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
from uvitools.broadcast import BroadcastMiddleware


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

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[asgi]: http://channels.readthedocs.io/en/stable/asgi.html
[asgi-message]: http://channels.readthedocs.io/en/stable/asgi/www.html#http-websocket-asgi-message-format-draft-spec
[request-body-chunk]: http://channels.readthedocs.io/en/stable/asgi/www.html#request-body-chunk
[response-chunk]: http://channels.readthedocs.io/en/stable/asgi/www.html#response-chunk
[http-message]: http://channels.readthedocs.io/en/stable/asgi/www.html#http
[websocket-message]: http://channels.readthedocs.io/en/latest/asgi/www.html#websocket
