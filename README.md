<p align="center">
  <img width="320" height="320" src="https://raw.githubusercontent.com/tomchristie/uvicorn/master/docs/uvicorn.png" alt='uvicorn'>
</p>

<p align="center">
<em>The lightning-fast ASGI server.</em>
</p>

---

[![Build Status](https://travis-ci.org/encode/uvicorn.svg?branch=master)](https://travis-ci.org/encode/uvicorn)
[![Coverage](https://codecov.io/gh/encode/uvicorn/branch/master/graph/badge.svg)](https://codecov.io/gh/encode/uvicorn)
[![Package version](https://badge.fury.io/py/uvicorn.svg)](https://pypi.python.org/pypi/uvicorn)

**Documentation**: [https://www.uvicorn.org](https://www.uvicorn.org)

**Requirements**: Python 3.5, 3.6, 3.7

Uvicorn is a lightning-fast ASGI server implementation, using [uvloop][uvloop] and [httptools][httptools].

Until recently Python has lacked a minimal low-level server/application interface for
asyncio frameworks. The [ASGI specification][asgi] fills this gap, and means we're now able to
start building a common set of tooling usable across all asyncio frameworks.

Uvicorn currently supports HTTP/1.1 and WebSockets. Support for HTTP/2 is planned.

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

    async def __call__(self, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [
                [b'content-type', b'text/plain'],
            ],
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

---

<p align="center"><i>Uvicorn is <a href="https://github.com/encode/uvicorn/blob/master/LICENSE.md">BSD licensed</a> code.<br/>Designed & built in Brighton, England.</i><br/>&mdash; 🦄  &mdash;</p>

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[asgi]: https://github.com/django/asgiref/blob/master/specs/asgi.rst
