# Settings

Use the following options to configure Uvicorn, when running from the command line.

If you're running using programmatically, using `uvicorn.run(...)`, then use
equivalent keyword arguments, eg. `uvicorn.run(app, port=5000, debug=True, access_log=False)`.

## Application

* `APP` - The ASGI application to run, in the format `"<module>:<attribute>"`.

## Socket Binding

* `--host <str>` - Bind socket to this host. Use `--host 0.0.0.0` to make the application available on your local network. **Default:** *'127.0.0.1'*.
* `--port <int>` - Bind to a socket with this port. **Default:** *8000*.
* `--uds <str>` - Bind to a UNIX domain socket. Useful if you want to run Uvicorn behind a reverse proxy.
* `--fd <int>` - Bind to socket from this file descriptor. Useful if you want to run Uvicorn within a process manager.

## Development

* `--reload` - Enable auto-reload.
* `--reload-dir <path>` - Specify which directories to watch for python file changes. May be used multiple times. If unused, then by default all directories in `sys.path` will be watched.

## Production

* `--workers <int>` - Use multiple worker processes.

## Logging

* `--log-level <str>` - Set the log level. **Options:** *'critical', 'error', 'warning', 'info', 'debug'.* **Default:** *'info'*.
* `--no-access-log` - Disable access log only, without changing log level.

## Implementation

* `--loop <str>` - Set the event loop implementation. The uvloop implementation provides greater performance, but is not compatible with Windows or PyPy. But you can use IOCP in windows. **Options:** *'auto', 'asyncio', 'uvloop', 'iocp'.* **Default:** *'auto'*.
* `--http <str>` - Set the HTTP protocol implementation. The httptools implementation provides greater performance, but it not compatible with PyPy, and requires compilation on Windows. **Options:** *'auto', 'h11', 'httptools'.* **Default:** *'auto'*.
* `--ws <str>` - Set the WebSockets protocol implementation. Either of the `websockets` and `wsproto` packages are supported. Use `'none'` to deny all websocket requests. **Options:** *'auto', 'none', 'websockets', 'wsproto'.* **Default:** *'auto'*.
* `--lifespan <str>` - Set the Lifespan protocol implementation. **Options:** *'auto', 'on', 'off'.* **Default:** *'auto'*.

## Application Interface

* `--interface` - Select ASGI3, ASGI2, or WSGI as the application interface.
Note that WSGI mode always disables WebSocket support, as it is not supported by the WSGI interface.
**Options:** *'auto', 'asgi3', 'asgi2', 'wsgi'.* **Default:** *'auto'*.

## HTTP

* `--root-path <str>` - Set the ASGI `root_path` for applications submounted below a given URL path.
* `--proxy-headers` - Use the X-Forwarded-Proto and X-Forwarded-For headers to populate remote scheme/address info.

## HTTPS

* `--ssl-keyfile <path>` - SSL key file
* `--ssl-certfile <path>` - SSL certificate file
* `--ssl-version <int>` - SSL version to use (see stdlib ssl module's)
* `--ssl-cert-reqs <int>` - Whether client certificate is required (see stdlib ssl module's)
* `--ssl-ca-certs <str>` - CA certificates file
* `--ssl-ciphers <str>` - Ciphers to use (see stdlib ssl module's)

## Resource Limits

* `--limit-concurrency <int>` - Maximum number of concurrent connections or tasks to allow, before issuing HTTP 503 responses. Useful for ensuring known memory usage patterns even under over-resourced loads.
* `--limit-max-requests <int>` - Maximum number of requests to service before terminating the process. Useful when running together with a process manager, for preventing memory leaks from impacting long-running processes.

## Timeouts

* `--timeout-keep-alive <int>` - Close Keep-Alive connections if no new data is received within this timeout. **Default:** *5*.
