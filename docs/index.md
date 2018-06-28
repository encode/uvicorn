# Introduction

Uvicorn is a lightning-fast ASGI server, built on [uvloop][uvloop] and [httptools][httptools].

Until recently Python has lacked a minimal low-level server/application interface for
asyncio frameworks. The [ASGI specification][asgi] fills this gap, and means we're now able to start building
a common set of tooling usable across all asyncio frameworks.

ASGI should help enable an ecosystem of Python web frameworks that are highly competitive against Node
and Go in terms of achieving high throughput in IO-bound contexts. It also provides support for HTTP/2 and
WebSockets, which cannot be handled by WSGI.

Uvicorn currently supports HTTP/1.1 and WebSockets. Support for HTTP/2 is planned.

## Quickstart

Requirements: Python 3.5.3+

Install using `pip`:

```shell
$ pip install uvicorn
```

Create an application, in `app.py`:

```python
class App():
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': b'Hello, world!',
        })
```

Run the server:

```shell
$ uvicorn app:App
```

# Usage

The uvicorn command line tool is the easiest way to run your application...

## Command line options

```shell
Usage: uvicorn [OPTIONS] APP

Options:
  --host TEXT                     Host
  --port INTEGER                  Port
  --loop [uvloop|asyncio]         Event loop
  --http [httptools|h11]          HTTP Handler
  --workers INTEGER               Number of worker processes
  --log-level [debug|info|warning|error|critical]
                                  Log level
  --help                          Show this message and exit.
```

Uvicorn currently includes two HTTP implementations, "httptools" and "h11".

It also supports two different event loop implementations, "uvloop" and
Python's standard "asyncio".

The default configuration is to use httptools and uvloop. If you need to
run under [PyPy][pypy], then you should switch to h11 and asyncio.

## Running programmatically

To run uvicorn directly from your application...

```python
import uvicorn

...

if __name__ == "__main__":
    uvicorn.run("127.0.0.1", 5000, log_level="info")
```

## Running with Gunicorn

[Gunicorn][gunicorn] is a mature, fully featured server and process manager.

Uvicorn includes a Gunicorn worker class allowing you to run ASGI applications,
with all of Uvicorn's performance benefits, while also giving you Gunicorn's
fully-featured process management.

This allows you to increase or decrease the number of worker processes on the
fly, restart worker processes gracefully, or perform server upgrades without downtime.

For production deployments we recommend using gunicorn with the uvicorn worker class.

```
gunicorn app:App -w 4 -k uvicorn.workers.UvicornWorker
```

For a [PyPy][pypy] compatible configuration use `uvicorn.workers.UvicornH11Worker`.

# The ASGI interface

Uvicorn uses the [ASGI specification][asgi] for interacting with an application.

The application should expose a callable which takes one argument, `scope`.
This callable is used to create a new instance of the application for each incoming connection.
It must return a coroutine which the server can then call into.

The application instance coroutine takes two arguments, `(receive, send)`,
which are the channels by which messages are sent between the web server and client application.

One style of implementation is to use a class with an `__init__()` method to handle
application instantiation, and a `__call__()` coroutine to provide the application implementation.

```python
class App():
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        ...
```

The content of the `scope` argument, and the messages expected by `receive` and `send` depend on
the protocol being used.

The format for HTTP messages is described in the [ASGI HTTP Message format][asgi-http].

## HTTP Scope

An incoming HTTP request might instantiate an application with the following `scope`:

```python
{
    'type': 'http.request',
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

## HTTP Messages

The instance coroutine communicates back to the server by sending messages to the `send` coroutine.

```python
await send({
    'type': 'http.request.start',
    'status': 200,
    'headers': [
        [b'content-type', b'text/plain'],
    ]
})
await send({
    'type': 'http.request.body',
    'body': b'Hello, world!',
})
```

# Requests & responses

Here's an example that displays the method and path used in the incoming request:

```python
class EchoMethodAndPath():
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, recieve, send):
        body = 'Received %s request to %s' % (self.scope['method'], self.scope['path'])
        await send({
            'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': body.encode('utf-8'),
        })
```

## Reading the request body

You can stream the request body without blocking the asyncio task pool,
by fetching messages from the `receive` coroutine.

```python
class EchoBody():
    def __init__(self, scope):
        self.scope = scope

    async def read_body(self, receive):
        """
        Read and return the entire body from an incoming ASGI message.
        """
        body = b''
        more_body = True

        while more_body:
            message = await receive()
            body += message.get('body', b'')
            more_body = message.get('more_body', False)

        return body


    async def __call__(self, receive, send):
        body = await self.read_body(receive)
        await send({
            'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ]
        })
        await send({
            'type': 'http.response.body',
            'body': body,
        })
```

## Streaming responses

You can stream responses by sending multiple `http.response.body` messages to
the `send` coroutine.

```python
class StreamResponse():
    def __init__(self, scope):
        self.scope = scope

    async def __call__(self, receive, send):
        body = await self.read_body(receive)
        await send({
            'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ]
        })
        for chunk in [b'Hello', b', ', b'world!']
            await send({
                'type': 'http.response.body',
                'body': chunk,
                'more_body': True
            })
        await send({
            'type': 'http.response.body',
            'body': b'',
        })
```

---

# Alternative ASGI servers

## Daphne

The first ASGI server implementation, originally developed to power Django Channels,
is [the Daphne webserver][daphne].

It is run widely in production, and supports HTTP/1.1, HTTP/2, and WebSockets.

Any of the example applications given here can equally well be run using `daphne` instead.

```shell
$ pip install daphne
$ daphne app:App
```

## Hypercorn

[Hypercorn][hypercorn] was initially part of the Quart web framework, before
being separated out into a standalone ASGI server.

```shell
$ pip install hypercorn
$ hypercorn app:App
```

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[gunicorn]: http://gunicorn.org/
[pypy]: https://pypy.org/
[asgi]: https://asgi.readthedocs.io/en/latest/
[asgi-http]: https://asgi.readthedocs.io/en/latest/specs/www.html
[daphne]: https://github.com/django/daphne
[hypercorn]: https://gitlab.com/pgjones/hypercorn
