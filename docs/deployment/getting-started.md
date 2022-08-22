# Deployment

Server deployment is a complex area, that will depend on what kind of service you're deploying Uvicorn onto.

### TL;DR
As a general rule, you probably want to:

* Run `uvicorn --reload` from the command line for local development.
* Run `gunicorn -k uvicorn.workers.UvicornWorker` for production (non containerized).
* Run behind Nginx for self-hosted deployments.
* Finally, run everything behind a CDN for caching support, and serious DDOS protection.

## Quick Start

This section is meant to get you started serving an ASGI application as quick as possible. ASGI applications are applications that adhere to the [ASGI Specification], which is the contract between the ASGI server (Uvicorn) and the ASGI application. Starlette  is just one ASGI framework amongst many, see [awesome-asgi] for a listing of some of the others.

[ASGI Specification]: https://asgi.readthedocs.io/en/latest/
[awesome-asgi]: https://github.com/florimondmanca/awesome-asgi

The following are ideal for running your application in a development environment.

### Running from the command line

The simplest way to run `uvicorn` is from the command line.

```bash
$ uvicorn example:app --reload --port 5000
```

The ASGI application should be specified in the form `path.to.module:instance.path`

Use `--reload` to turn on auto-reloading. 
???+ note
    `--reload` is recommended only for local use, during the development phase.
    
    The `--reload` and `--workers` arguments are **mutually exclusive**.




To see the complete set of available options, use `uvicorn --help`:

<!-- :cli_usage: -->
```
$ uvicorn --help
Usage: uvicorn [OPTIONS] APP

Options:
  --host TEXT                     Bind socket to this host.  [default:
                                  127.0.0.1]
  --port INTEGER                  Bind socket to this port.  [default: 8000]
  --uds TEXT                      Bind to a UNIX domain socket.
  --fd INTEGER                    Bind to socket from this file descriptor.
  --reload                        Enable auto-reload.
  --reload-dir PATH               Set reload directories explicitly, instead
                                  of using the current working directory.
  --reload-include TEXT           Set glob patterns to include while watching
                                  for files. Includes '*.py' by default; these
                                  defaults can be overridden with `--reload-
                                  exclude`. This option has no effect unless
                                  watchfiles is installed.
  --reload-exclude TEXT           Set glob patterns to exclude while watching
                                  for files. Includes '.*, .py[cod], .sw.*,
                                  ~*' by default; these defaults can be
                                  overridden with `--reload-include`. This
                                  option has no effect unless watchfiles is
                                  installed.
  --reload-delay FLOAT            Delay between previous and next check if
                                  application needs to be. Defaults to 0.25s.
                                  [default: 0.25]
  --workers INTEGER               Number of worker processes. Defaults to the
                                  $WEB_CONCURRENCY environment variable if
                                  available, or 1. Not valid with --reload.
  --loop [auto|asyncio|uvloop]    Event loop implementation.  [default: auto]
  --http [auto|h11|httptools]     HTTP protocol implementation.  [default:
                                  auto]
  --ws [auto|none|websockets|wsproto]
                                  WebSocket protocol implementation.
                                  [default: auto]
  --ws-max-size INTEGER           WebSocket max size message in bytes
                                  [default: 16777216]
  --ws-ping-interval FLOAT        WebSocket ping interval  [default: 20.0]
  --ws-ping-timeout FLOAT         WebSocket ping timeout  [default: 20.0]
  --ws-per-message-deflate BOOLEAN
                                  WebSocket per-message-deflate compression
                                  [default: True]
  --lifespan [auto|on|off]        Lifespan implementation.  [default: auto]
  --interface [auto|asgi3|asgi2|wsgi]
                                  Select ASGI3, ASGI2, or WSGI as the
                                  application interface.  [default: auto]
  --env-file PATH                 Environment configuration file.
  --log-config PATH               Logging configuration file. Supported
                                  formats: .ini, .json, .yaml.
  --log-level [critical|error|warning|info|debug|trace]
                                  Log level. [default: info]
  --access-log / --no-access-log  Enable/Disable access log.
  --use-colors / --no-use-colors  Enable/Disable colorized logging.
  --proxy-headers / --no-proxy-headers
                                  Enable/Disable X-Forwarded-Proto,
                                  X-Forwarded-For, X-Forwarded-Port to
                                  populate remote address info.
  --server-header / --no-server-header
                                  Enable/Disable default Server header.
  --date-header / --no-date-header
                                  Enable/Disable default Date header.
  --forwarded-allow-ips TEXT      Comma separated list of IPs to trust with
                                  proxy headers. Defaults to the
                                  $FORWARDED_ALLOW_IPS environment variable if
                                  available, or '127.0.0.1'.
  --root-path TEXT                Set the ASGI 'root_path' for applications
                                  submounted below a given URL path.
  --limit-concurrency INTEGER     Maximum number of concurrent connections or
                                  tasks to allow, before issuing HTTP 503
                                  responses.
  --backlog INTEGER               Maximum number of connections to hold in
                                  backlog
  --limit-max-requests INTEGER    Maximum number of requests to service before
                                  terminating the process.
  --timeout-keep-alive INTEGER    Close Keep-Alive connections if no new data
                                  is received within this timeout.  [default:
                                  5]
  --ssl-keyfile TEXT              SSL key file
  --ssl-certfile TEXT             SSL certificate file
  --ssl-keyfile-password TEXT     SSL keyfile password
  --ssl-version INTEGER           SSL version to use (see stdlib ssl module's)
                                  [default: 17]
  --ssl-cert-reqs INTEGER         Whether client certificate is required (see
                                  stdlib ssl module's)  [default: 0]
  --ssl-ca-certs TEXT             CA certificates file
  --ssl-ciphers TEXT              Ciphers to use (see stdlib ssl module's)
                                  [default: TLSv1]
  --header TEXT                   Specify custom default HTTP response headers
                                  as a Name:Value pair
  --version                       Display the uvicorn version and exit.
  --app-dir TEXT                  Look for APP in the specified directory, by
                                  adding this to the PYTHONPATH. Defaults to
                                  the current working directory.  [default: .]
  --h11-max-incomplete-event-size INTEGER
                                  For h11, the maximum number of bytes to
                                  buffer of an incomplete event.
  --factory                       Treat APP as an application factory, i.e. a
                                  () -> <ASGI app> callable.
  --help                          Show this message and exit.
```


See the [settings documentation](../settings.md) for more details on the supported options for running uvicorn.

### Running programmatically

Uvicorn can also be run programmatically. To run directly from within a Python program, you should use `uvicorn.run(app, **config)`. 

**`example.py`**

```python
import uvicorn

class App:
    ...

app = App()

if __name__ == "__main__":
    uvicorn.run("example:app", host="127.0.0.1", port=5000, log_level="info")
```

The set of configuration options available is the same as for the options listed under running from commandline.

!!! note
    Note that the application instance itself *can* be passed instead of the app
    import string.

    ```python
    uvicorn.run(app, host="127.0.0.1", port=5000, log_level="info")
    ```

    However, this style only works if you are not using multiprocessing (`workers=NUM`)
    or reloading (`reload=True`), so we recommend using the import string style.

    Also note that in this case, you should put `uvicorn.run` into `if __name__ == '__main__'` clause in the main module.

    The `reload` and `workers` parameters are **mutually exclusive**.

