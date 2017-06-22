<p align="center">
  <img width="320" height="320" src="https://raw.githubusercontent.com/tomchristie/uvicorn/master/docs/uvicorn.png" alt='uvicorn'>
</p>

<p align="center">
<em>The lightning-fast asyncio server, for Python 3.</em>
</p>

---

**Documentation**: [http://www.uvicorn.org](http://www.uvicorn.org)

**Requirements**: Python 3.5.3+

Python currently lacks a minimal low-level server/application interface for
asyncio frameworks. Filling this gap means we'd be able to start building
a common set of tooling usable across all asyncio frameworks.

Uvicorn is an attempt to resolve this, by providing:

* A lightning-fast asyncio server implementation, using [uvloop][uvloop] and [httptools][httptools].
* A minimal application interface, based on [ASGI][asgi].

It currently supports HTTP, WebSockets, Pub/Sub broadcast, and is open
to extension to other protocols & messaging styles.

## Quickstart

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

---

<p align="center"><i>Uvicorn is <a href="https://github.com/encode/uvicorn/blob/master/LICENSE.md">BSD licensed</a> code.<br/>Designed & built in Brighton, England.</i><br/>&mdash; 🦄  &mdash;</p>

[uvloop]: https://github.com/MagicStack/uvloop
[httptools]: https://github.com/MagicStack/httptools
[asgi]: http://channels.readthedocs.io/en/stable/asgi.html
