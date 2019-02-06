# Settings

Use the following options to configure Uvicorn, when running from the command line.

If you're running using programmatically, using `uvicorn.run(...)`, then use
equivalent keyword arguments, eg. `uvicorn.run(App, port=5000, debug=True, access_log=False)`.

## Application

* `APP` - The ASGI application to run, in the format `"<module>:<attribute>"`.

## Socket Binding

* `--host` - Bind socket to this host. Use `--host 0.0.0.0` to make the application available on your local network. **Default:** *'127.0.0.1'*.
* `--port` - Bind to a socket with this port. **Default:** *8000*.
* `--uds` - Bind to a UNIX domain socket. Useful if you want to run Uvicorn behind a reverse proxy.
* `--fd` - Bind to socket from this file descriptor. Useful if you want to run Uvicorn within a process manager.

## Development

* `--debug` - Enable debug mode. Provides error tracebacks in the browser, and enables auto-reloading.

## Logging

* `--log-level` - Set the log level. **Options:** *'critical', 'error', 'warning', 'info', 'debug'.* **Default:** *'info'*.
* `--no-access-log` - Disable access log only, without changing log level.

## Implementation

* `--loop` - Set the event loop implementation. The uvloop implementation provides greater performance, but is not compatible with Windows or PyPy. **Options:** *'auto', 'asyncio', 'uvloop'.* **Default:** *'auto'*.
* `--http` - Set the HTTP protocol implementation. The httptools implementation provides greater performance, but it not compatible with PyPy, and requires compilation on Windows. **Options:** *'auto', 'h11', 'httptools'.* **Default:** *'auto'*.
* `--ws` - Set the WebSockets protocol implementation. Either of the `websockets` and `wsproto` packages are supported. Use `'none'` to deny all websocket requests. **Options:** *'auto', 'none', 'websockets', 'wsproto'.* **Default:** *'auto'*.

## Application Interface

* `--wsgi` - Use WSGI as the application interface rather than ASGI. Note that WSGI mode always disables WebSocket support, as it is not supported by the WSGI interface.

## HTTP

* `--root-path` - Set the ASGI `root_path` for applications submounted below a given URL path.
* `--proxy-headers` - Use the X-Forwarded-Proto and X-Forwarded-For headers to populate remote scheme/address info.

## HTTPS

* `--ssl-keyfile` - SSL key file
* `--ssl-certfile` - SSL certificate file
* `--ssl-version` - SSL version to use (see stdlib ssl module's)
* `--ssl-cert-reqs` - Whether client certificate is required (see stdlib ssl module's)
* `--ssl-ca-certs` - CA certificates file
* `--ssl-ciphers` - Ciphers to use (see stdlib ssl module's)

## Resource Limits

* `--limit-concurrency` - Maximum number of concurrent connections or tasks to allow, before issuing HTTP 503 responses. Useful for ensuring known memory usage patterns even under over-resourced loads.
* `--limit-max-requests` - Maximum number of requests to service before terminating the process. Useful when running together with a process manager, for preventing memory leaks from impacting long-running processes.

## Timeouts

* `--timeout-keep-alive` - Close Keep-Alive connections if no new data is received within this timeout. **Default:** *5*.

## Lifespan

* `--disable-lifespan` - Disable lifespan events (such as startup and shutdown) within an ASGI application.
