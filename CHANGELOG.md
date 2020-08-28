# Change Log

## 0.11.9 - 2020-08-28

### Added
- Upgrade maximum h11 dependency version to 0.10 (#772) 8/28/20 54d729cc
- Allow .json or .yaml --log-config files (#665) 8/18/20 093a1f7c
- Added asgi dict to the lifespan scope (#754) 8/15/20 8150c3eb
- Upgrade wsproto to 0.15.0 (#750) 8/13/20 fbce393f
- Use optional package installs (#666) 8/10/20 5fa99a11

### Changed
- Dont set log level for root logger (#767) 8/28/20 df81b168

### Fixed
- Revert "Improve shutdown robustness when using `--reload` or multiprocessing (#620)" (#756) 8/28/20 ff4af12d
- Fix terminate error in windows (#744) 8/27/20 dd3b842d
- Fixes bug where --log-config disables uvicorn loggers (#512) 8/11/20 a9c37cc4

## 0.11.8 - 2020-07-30

* Fix a regression that caused Uvicorn to crash when using `--interface=wsgi`. (Pull #730)
* Fix a regression that caused Uvicorn to crash when using unix domain sockets. (Pull #729)

## 0.11.7 - 2020-28-07

* SECURITY FIX: Prevent sending invalid HTTP header names and values. (Pull #725)
* SECURITY FIX: Ensure path value is escaped before logging to the console. (Pull #724)
* Fix `--proxy-headers` client IP and host when using a Unix socket. (Pull #636)

## 0.11.6

* Fix overriding the root logger.

## 0.11.5

* Revert "Watch all files, not just .py" due to unexpected side effects.
* Revert "Pass through gunicorn timeout config." due to unexpected side effects.

## 0.11.4

* Use `watchgod`, if installed, for watching code changes.
* Watch all files, not just .py.
* Pass through gunicorn timeout config.

## 0.11.3

* Update dependencies.

## 0.11.2

* Don't open socket until after application startup.
* Support `--backlog`.

## 0.11.1

* Use a more liberal `h11` dependency. Either `0.8.*` or `0.9.*``.

## 0.11.0

* Fix reload/multiprocessing on Windows with Python 3.8.
* Drop IOCP support. (Required for fix above.)
* Add `uvicorn --version` flag.
* Add `--use-colors` and `--no-use-colors` flags.
* Display port correctly, when auto port selection isused with `--port=0`.

## 0.10.8

* Fix reload/multiprocessing error.

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
