# ASGIWorker

*An ASGI worker class for Gunicorn.*

A Gunicorn worker class that interfaces with an ASGI Consumer callable, rather than a WSGI callable.

We use a couple of packages from MagicStack in order to achieve an extremely high-throughput and low-latency implementation:

* `uvloop` as the event loop policy.
* `httptools` as the HTTP request parser.

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
* Streaming responses could be supported without much work. The handler function
is already free to call `.send(...)` any number of times.
