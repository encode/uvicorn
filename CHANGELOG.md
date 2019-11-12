# Change Log

## 0.10.7

* Use resource_sharer.DupSocket to resolve socket sharing on Windows.

## 0.10.6

* Exit if `workers` or `reload` are use without an app import string style.
* Reorganise supervisor processes to properly hand over sockets on windows.

## 0.10.5

* Update uvloop dependency to 0.14+

## 0.10.4

* Error clearly when `workers=<NUM>` is used with app instance, instead of an app import string.
* Switch `--reload-dir` to current working directory by default.

## 0.10.3

* Add ``--log-level trace`

## 0.10.2

* Enable --proxy-headers by default.

## 0.10.1

* Resolve issues with logging when using `--reload` or `--workers`.
* Setup up root logger to capture output for all logger instances, not just `uvicorn.error` and `uvicorn.access`.

## 0.10.0

* Support for Python 3.8
* Separated out `uvicorn.error` and `uvicorn.access` logs.
* Coloured log output when connected to a terminal.
* Dropped `logger=` config setting.
* Added `--log-config [FILE]` and `log_config=[str|dict]`. May either be a Python logging config dictionary or the file name of a logging configuration.
* Added `--forwarded_allow_ips` and `forwarded_allow_ips`. Defaults to the value of the `$FORWARDED_ALLOW_IPS` environment variable or "127.0.0.1". The `--proxy-headers` flag now defaults to `True`, but only trusted IPs are used to populate forwarding info.
* The `--workers` setting now defaults to the value of the `$WEB_CONCURRENCY` environment variable.
* Added support for `--env-file`. Requires `python-dotenv`.
