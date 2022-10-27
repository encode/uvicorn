# Logging

**Uvicorn** has three logger objects available:

* **ASGI Logger** (`uvicorn.asgi`) - Low level ASGI application logs.
* **Access Logger** (`uvicorn.access`) - HTTP access logs.
* **Main Logger**: `uvicorn.error` - Everything else, **not only errors**.

## ASGI Logger

The **ASGI logger** is used to log low level ASGI interactions.

This logger is useful to **debug ASGI applications**, and to understand how **Uvicorn interacts** with them.
To be able to see its logs, set **`--log-level`** to **`trace`**.

Let's understand a bit better with an example. Assume we have the following ASGI application:

```py title="main.py"
async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"text/plain"]],
    })
    await send({"type": "http.response.body", "body": b"Hello, world!"})
```

Let's run it with the following command:

```bash
uvicorn main:app --log-level trace
```

You'll see the following output:

```bash
INFO:     Started server process [73010]
INFO:     Waiting for application startup.
TRACE:    ASGI [1] Started scope={'type': 'lifespan', 'asgi': {'version': '3.0', 'spec_version': '2.0'}}
TRACE:    ASGI [1] Raised exception
INFO:     ASGI 'lifespan' protocol appears unsupported.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

In case you send a request to the server, you'll see the following output:

```bash
TRACE:    127.0.0.1:45540 - HTTP connection made
TRACE:    127.0.0.1:45540 - ASGI [2] Started scope={'type': 'http', 'asgi': {'version': '3.0', 'spec_version': '2.3'}, 'http_version': '1.1', 'server': ('127.0.0.1', 8000), 'client': ('127.0.0.1', 45540), 'scheme': 'http', 'root_path': '', 'headers': '<...>', 'method': 'GET', 'path': '/', 'raw_path': b'/', 'query_string': b''}
TRACE:    127.0.0.1:45540 - ASGI [2] Send {'type': 'http.response.start', 'status': 200, 'headers': '<...>'}
INFO:     127.0.0.1:45540 - "GET / HTTP/1.1" 200 OK
TRACE:    127.0.0.1:45540 - ASGI [2] Send {'type': 'http.response.body', 'body': '<13 bytes>'}
TRACE:    127.0.0.1:45540 - ASGI [2] Completed
TRACE:    127.0.0.1:45540 - HTTP connection lost
```

## Access Logger

The **Access Logger** is used to log HTTP access logs.

This logger is called **every time a response is sent** to a client. It's useful to **monitor HTTP traffic**.

### Access Log Format

The default access log format is:

```bash
%(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s
```

The following variables are available:

- **`client_addr`**: The client IP address.
- **`status_code`**: The response status code (e.g. `200 OK`).
- **`method`**: The request method.
- **`full_path`**: The full request path (e.g. `/foo?bar=baz`).
- **`http_version`**: The HTTP version (e.g. `HTTP/1.1`).
- **`request_line`**: The request line (e.g. `GET /foo?bar=baz HTTP/1.1`).

## Main Logger

The **Main Logger** is used to log everything else, **not only errors**.

This logger is useful to **monitor Uvicorn** itself, and to understand what's going on.
