<p align="center">
  <img width="320" height="320" src="https://raw.githubusercontent.com/tomchristie/uvicorn/master/docs/uvicorn.png" alt='uvicorn'>
</p>

<p align="center">
<em>The lightning-fast asyncio server, for Python 3.</em>
</p>

---

[![Build Status](https://travis-ci.org/encode/uvicorn.svg?branch=master)](https://travis-ci.org/encode/uvicorn)
[![Package version](https://badge.fury.io/py/uvicorn.svg)](https://pypi.python.org/pypi/uvicorn)
[![Python versions](https://img.shields.io/pypi/pyversions/uvicorn.svg)](https://www.python.org/doc/versions/)

**Documentation**: [http://www.uvicorn.org](http://www.uvicorn.org)

**Requirements**: Python 3.5.3+

Until recently Python has lacked a minimal low-level server/application interface for
asyncio frameworks. The ASGI specification fills this gap, and means we're now able to start building
a common set of tooling usable across all asyncio frameworks.

Uvicorn is a lightning-fast ASGI server implementation, using [uvloop][uvloop] and [httptools][httptools].

It currently only supports HTTP/1.1, but WebSocket support and HTTP/2 are planned.

## Quickstart

Install using `pip`:

```shell
$ pip install uvicorn
```

Create an application, in `app.py`:

```python
class App():
    def __init__(self, scope):
        self.scope = scope

    async def __call__(receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ],
        })
        await send({
            'type': 'http.response.body',
            'body': 'Hello, world!',
        })
```

Run the server:

```shell
$ uvicorn app:App
```

## Alternative ASGI servers

[The `daphne` webserver][daphne] was the first ASGI webserver implementation.
It is run widely in production, and supports HTTP1.1, HTTP2, and WebSockets.

We can equally well run our example application using `daphne` instead.

```shell
$ pip install daphne
$ daphne app:App
```

## Motivation

ASGI enables an ecosystem of Python web frameworks that are competitive against Node and Go in terms
of achieving high throughput in IO-bound contexts.

It provides support for HTTP/2 and WebSockets, which cannot be handled by WSGI. Together with message
queues such as Django Channels, it can also be used to bring support for these protocols to
existing multi-threaded web frameworks.

ASGI is also an extensible, general-purpose messaging interface for building event-driven systems.

---

<p align="center"><i>Uvicorn is <a href="https://github.com/encode/uvicorn/blob/master/LICENSE.md">BSD licensed</a> code.<br/>Designed & built in Brighton, England.</i><br/>&mdash; 🦄  &mdash;</p>

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[asgi]: http://channels.readthedocs.io/en/stable/asgi.html
[daphne]: https://github.com/django/daphne
