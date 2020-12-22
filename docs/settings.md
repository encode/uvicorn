# Settings

Use the following options to configure Uvicorn, when running from the command line.

If you're running using programmatically, using `uvicorn.run(...)`, then use
equivalent keyword arguments, eg. `uvicorn.run("example:app", port=5000, reload=True, access_log=False)`.

## Application

* `APP` - The ASGI application to run, in the format `"<module>:<attribute>"`.
* `--factory` - Treat `APP` as an application factory, i.e. a `() -> <ASGI app>` callable.

## Socket Binding

* `--host <str>` - Bind socket to this host. Use `--host 0.0.0.0` to make the application available on your local network. IPv6 addresses are supported, for example: `--host '::'`. **Default:** *'127.0.0.1'*.
* `--port <int>` - Bind to a socket with this port. **Default:** *8000*.
* `--uds <str>` - Bind to a UNIX domain socket. Useful if you want to run Uvicorn behind a reverse proxy.
* `--fd <int>` - Bind to socket from this file descriptor. Useful if you want to run Uvicorn within a process manager.

## Development

* `--reload` - Enable auto-reload.
* `--reload-dir <path>` - Specify which directories to watch for python file changes. May be used multiple times. If unused, then by default all directories in current directory will be watched.

## Production

* `--workers <int>` - Use multiple worker processes. Defaults to the value of the `$WEB_CONCURRENCY` environment variable.

## Logging

* `--log-config <path>` - Logging configuration file. **Options:** *`dictConfig()` formats: .json, .yaml*. Any other format will be processed with `fileConfig()`. Set the `formatters.default.use_colors` and `formatters.access.use_colors` values to override the auto-detected behavior.
    * If you wish to use a YAML file for your logging config, you will need to include PyYAML as a dependency for your project or install uvicorn with the `[standard]` optional extras.
* `--log-level <str>` - Set the log level. **Options:** *'critical', 'error', 'warning', 'info', 'debug', 'trace'.* **Default:** *'info'*.
* `--no-access-log` - Disable access log only, without changing log level.
* `--use-colors / --no-use-colors` - Enable / disable colorized formatting of the log records, in case this is not set it will be auto-detected. This option is ignored if the `--log-config` CLI option is used.


## Implementation

* `--loop <str>` - Set the event loop implementation. The uvloop implementation provides greater performance, but is not compatible with Windows or PyPy. **Options:** *'auto', 'asyncio', 'uvloop'.* **Default:** *'auto'*.
* `--http <str>` - Set the HTTP protocol implementation. The httptools implementation provides greater performance, but it not compatible with PyPy, and requires compilation on Windows. **Options:** *'auto', 'h11', 'httptools'.* **Default:** *'auto'*.
* `--ws <str>` - Set the WebSockets protocol implementation. Either of the `websockets` and `wsproto` packages are supported. Use `'none'` to deny all websocket requests. **Options:** *'auto', 'none', 'websockets', 'wsproto'.* **Default:** *'auto'*.
* `--lifespan <str>` - Set the Lifespan protocol implementation. **Options:** *'auto', 'on', 'off'.* **Default:** *'auto'*.

## Application Interface

* `--interface` - Select ASGI3, ASGI2, or WSGI as the application interface.
Note that WSGI mode always disables WebSocket support, as it is not supported by the WSGI interface.
**Options:** *'auto', 'asgi3', 'asgi2', 'wsgi'.* **Default:** *'auto'*.

## HTTP

* `--root-path <str>` - Set the ASGI `root_path` for applications submounted below a given URL path.
* `--proxy-headers` / `--no-proxy-headers` - Enable/Disable X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to populate remote address info. Defaults to enabled, but is restricted to only trusting
connecting IPs in the `forwarded-allow-ips` configuration.
* `--forwarded-allow-ips` <comma-separated-list> Comma separated list of IPs to trust with proxy headers. Defaults to the `$FORWARDED_ALLOW_IPS` environment variable if available, or '127.0.0.1'. A wildcard '*' means always trust.

## HTTPS

* `--ssl-keyfile <path>` - SSL key file
* `--ssl-keyfile-password <str>` - Password to decrypt the ssl key
* `--ssl-certfile <path>` - SSL certificate file
* `--ssl-version <int>` - SSL version to use (see stdlib ssl module's)
* `--ssl-cert-reqs <int>` - Whether client certificate is required (see stdlib ssl module's)
* `--ssl-ca-certs <str>` - CA certificates file
* `--ssl-ciphers <str>` - Ciphers to use (see stdlib ssl module's)

## Resource Limits

* `--limit-concurrency <int>` - Maximum number of concurrent connections or tasks to allow, before issuing HTTP 503 responses. Useful for ensuring known memory usage patterns even under over-resourced loads.
* `--limit-max-requests <int>` - Maximum number of requests to service before terminating the process. Useful when running together with a process manager, for preventing memory leaks from impacting long-running processes.
* `--backlog <int>` - Maximum number of connections to hold in backlog. Relevant for heavy incoming traffic. **Default:** *2048*

## Timeouts

* `--timeout-keep-alive <int>` - Close Keep-Alive connections if no new data is received within this timeout. **Default:** *5*.
