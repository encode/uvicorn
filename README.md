<p align="center">
  <img width="350" height="350" src="https://raw.githubusercontent.com/tomchristie/uvicorn/master/docs/uvicorn.png" alt='uvicorn'>
</p>

<p align="center">
<em>A lightning-fast asyncio server for Python 3.</em>
</p>

---

## Installation

Install using `pip`:

    pip install uvicorn

## Examples

### Hello, world...

**app.py**:

```python
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
```

**Run the server**:

```shell
uvicorn app:hello_world
```

### Using async...

```python
import asyncio


async hello_world(message):
    await asyncio.sleep(1)
    content = b'<html><h1>Hello, world</h1></html>'
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
        ],
        'content': content
    }
    message['reply_channel'].send(response)
```

**Run the server**:

```shell
uvicorn app:hello_world
```

---

[Discussion on django-dev](https://groups.google.com/forum/#!topic/django-developers/_314PGl3Ao0).

The server is implemented as a Gunicorn worker class that interfaces with an
ASGI Consumer callable, rather than a WSGI callable.

We use a couple of packages from [MagicStack](https://github.com/MagicStack/) in
order to achieve an extremely high-throughput and low-latency implementation:

* `uvloop` as the event loop policy.
* `httptools` as the HTTP request parser.

You can use uvicorn to interface with either a traditional syncronous
application codebase, or an asyncio application codebase.

These are the same packages used by the [Sanic web framework](https://github.com/channelcat/sanic).

## Notes

* I've modified the ASGI consumer contract slightly, to allow coroutine functions.
This provides a nicer interface for asyncio implementations. It's not strictly
necessary to make this change as it's possible to instead have the application
be responsible for adding a new task to the event loop.
* Streaming responses are supported, using "Response Chunk" ASGI messages.
* Streaming requests are not currently supported.

## Comparative performance vs Meinheld

Using `wrk -d20s -t10 -c200 http://127.0.0.1:8080/` on a 2013 MacBook Air...

Server       | Requests/sec | Avg latency
-------------|--------------|------------
Uvicorn      |      ~34,000 |        ~6ms
Meinheld     |      ~16,000 |       ~12ms

## ASGI Consumers vs Channels.

This worker class interfaces directly with an ASGI Consumer.

This is in contrast to Django Channels, where server processes communicate
with worker processes via an intermediary channel layer.
