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

Install using `pip`:

    $ pip install uvicorn

Create an application:

**app.py**

```python
async hello_world(message, channels):
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

Uvicorn introduces a messaging interface based on ASGI...

* `message` is an [ASGI message][asgi-message].  (But see below for ammendments.)
* `channels` is a dictionary of <unicode string>:<channel interface>.

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
