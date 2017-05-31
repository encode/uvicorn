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
    message = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
            [b'content-length', str(len(content)).encode('ascii')]
        ],
        'content': content
    }
    message['reply_channel'].send(message)
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


async def sleepy_hello_world(message):
    await asyncio.sleep(1)
    content = b'<html><h1>Hello, world</h1></html>'
    message = {
        'status': 200,
        'headers': [
            [b'content-type', b'text/html'],
            [b'content-length', str(len(content)).encode('ascii')]
        ],
        'content': content
    }
    message['reply_channel'].send(message)
```

**Run the server**:

```shell
gunicorn app:hello_world --bind localhost:8080 --worker-class asgiworker.ASGIWorker
```
