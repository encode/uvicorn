# ASGIWorker

*An ASGI worker class for Gunicorn.*

[Discussion on django-dev](https://groups.google.com/forum/#!topic/django-developers/_314PGl3Ao0).

A Gunicorn worker class that interfaces with an ASGI Consumer callable, rather than a WSGI callable.

We use a couple of packages from [MagicStack](https://github.com/MagicStack/) in
order to achieve an extremely high-throughput and low-latency implementation:

* `uvloop` as the event loop policy.
* `httptools` as the HTTP request parser.

You can use this worker class to interface with either a traditional syncronous
application codebase, or an asyncronous application codebase using asyncio.

These are the same packages used by the [Sanic web framework](https://github.com/channelcat/sanic).

## Examples

### An ASGI consumer, returning "Hello, world".

**app.py**:

```python
def hello_world(message):
    content = b'<html><h1>Hello, world</h1></html>'
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
            [b'content-length', str(len(content)).encode('ascii')]
        ],
        'content': content
    }
    message['reply_channel'].send(response)
```

**Run the server**:

```shell
gunicorn app:hello_world --bind localhost:8080 --worker-class asgiworker.ASGIWorker
```

### An ASGI consumer, returning "Hello, world" after a (non-blocking) 1 second delay.

```python
import asyncio


def hello_world(message):
    loop = message['channel_layer'].loop
    loop.create_task(sleepy_hello_world(message))


async def sleepy_hello_world(response):
    await asyncio.sleep(1)
    content = b'<html><h1>Hello, world</h1></html>'
    response = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
            [b'content-length', str(len(content)).encode('ascii')]
        ],
        'content': content
    }
    message['reply_channel'].send(response)
```

**Run the server**:

```shell
gunicorn app:hello_world --bind localhost:8080 --worker-class asgiworker.ASGIWorker
```

## Notes

* We could allow ASGIWorker to (optionally) accept a co-routine directly, and
handle the `loop.create_task` dance itself. I've left things as-is right now
to demonstrate that it works without modifying the ASGI Consumer contract.
* I've included a `.loop` attribute on the channel_layer. This isn't strictly
neccessary, as we could call `asyncio.get_event_loop()`, but it'd be nice to
avoid that if we can.
* Streaming responses could be supported with minimal work. The handler function
is already free to call `.send(...)` any number of times, but we don't yet
handle the different message cases, and naively assume a single response message.

## Comparative performance vs Meinheld

Using `wrk -d20s -t10 -c200 http://127.0.0.1:8080/` on a 2013 MacBook Air...

Worker Class | Requests/sec | Avg latency
-------------|--------------|------------
ASGIWorker   |      ~34,000 |        ~6ms
Meinheld     |      ~16,000 |       ~12ms

Not *quite* a like-for-like as there's a few extra bits of processing currently
missing from ASGIWorker, but I don't believe there's anything that would add
significant overhead.

## ASGI Consumers vs Channels.

This worker class interfaces directly with an ASGI Consumer.

This is in contrast to Django Channels, where server processes communicate
with worker processes, via an intermediary channel layer.

This doesn't quite fit the original design intent behind ASGI, but the
introduction of a channel layer seems unneccessary for eg. HTTP requests.

We can still introduce backpressure, by capping a maximum number of allowable
concurrent connections, which as far as I can tell would have pretty much
an equivelent effect to capping the maximum number of allowable queued messages.
