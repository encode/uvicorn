# Change Log

## 0.30.3 (2024-07-20)

### Fixed

- Suppress `KeyboardInterrupt` from CLI and programmatic usage (#2384)
- `ClientDisconnect` inherits from `OSError` instead of `IOError` (#2393)

## 0.30.2 (2024-07-20)

### Added

- Add `reason` support to [`websocket.disconnect`](https://asgi.readthedocs.io/en/latest/specs/www.html#disconnect-receive-event-ws) event (#2324)

### Fixed

- Iterate subprocesses in-place on the process manager (#2373)

## 0.30.1 (2024-06-02)

### Fixed

- Allow horizontal tabs `\t` in response header values (#2345)

## 0.30.0 (2024-05-28)

### Added

- New multiprocess manager (#2183)
- Allow `ConfigParser` or a `io.IO[Any]` on `log_config` (#1976)

### Fixed

- Suppress side-effects of signal propagation (#2317)
- Send `content-length` header on 5xx (#2304)

### Deprecated

- Deprecate the `uvicorn.workers` module (#2302)

## 0.29.0 (2024-03-19)

### Added

- Cooperative signal handling (#1600)

## 0.28.1 (2024-03-19)

### Fixed

- Revert raise `ClientDisconnected` on HTTP (#2276)

## 0.28.0 (2024-03-09)

### Added

- Raise `ClientDisconnected` on `send()` when client disconnected (#2220)

### Fixed

- Except `AttributeError` on `sys.stdin.fileno()` for Windows IIS10 (#1947)
- Use `X-Forwarded-Proto` for WebSockets scheme when the proxy provides it (#2258)

## 0.27.1 (2024-02-10)

- Fix spurious LocalProtocolError errors when processing pipelined requests (#2243)

## 0.27.0.post1 (2024-01-29)

### Fixed

- Fix nav overrides for newer version of Mkdocs Material (#2233)

## 0.27.0 (2024-01-22)

### Added

- Raise `ClientDisconnect(IOError)` on `send()` when client disconnected (#2218)
- Bump ASGI WebSocket spec version to 2.4 (#2221)

## 0.26.0 (2024-01-16)

### Changed

- Update `--root-path` to include the root path prefix in the full ASGI `path` as per the ASGI spec (#2213)
- Use `__future__.annotations` on some internal modules (#2199)

## 0.25.0 (2023-12-17)

### Added

- Support the WebSocket Denial Response ASGI extension (#1916)

### Fixed

- Allow explicit hidden file paths on `--reload-include` (#2176)
- Properly annotate `uvicorn.run()` (#2158)

## 0.24.0.post1 (2023-11-06)

### Fixed

- Revert mkdocs-material from 9.1.21 to 9.2.6 (#2148)

## 0.24.0 (2023-11-04)

### Added

- Support Python 3.12 (#2145)
- Allow setting `app` via environment variable `UVICORN_APP` (#2106)

## 0.23.2 (2023-07-31)

### Fixed

- Maintain the same behavior of `websockets` from 10.4 on 11.0 (#2061)

## 0.23.1 (2023-07-18)

### Fixed

- Add `typing_extensions` for Python 3.10 and lower (#2053)

## 0.23.0 (2023-07-10)

### Added

- Add `--ws-max-queue` parameter WebSockets (#2033)

### Removed

- Drop support for Python 3.7 (#1996)
- Remove `asgiref` as typing dependency (#1999)

### Fixed

- Set `scope["scheme"]` to `ws` or `wss` instead of `http` or `https` on `ProxyHeadersMiddleware` for WebSockets (#2043)

### Changed

- Raise `ImportError` on circular import (#2040)
- Use `logger.getEffectiveLevel()` instead of `logger.level` to check if log level is `TRACE` (#1966)

## 0.22.0 (2023-04-28)

### Added

- Add `--timeout-graceful-shutdown` parameter (#1950)
- Handle `SIGBREAK` on Windows (#1909)

### Fixed

- Shutdown event is now being triggered on Windows when using hot reload (#1584)
- `--reload-delay` is effectively used on the `watchfiles` reloader (#1930)

## 0.21.1 (2023-03-16)

### Fixed

- Reset lifespan state on each request (#1903)

## 0.21.0 (2023-03-09)

### Added

- Introduce lifespan state (#1818)
- Allow headers to be sent as iterables on H11 implementation (#1782)
- Improve discoverability when --port=0 is used (#1890)

### Changed

- Avoid importing `h11` and `pyyaml` when not needed to improve import time (#1846)
- Replace current native `WSGIMiddleware` implementation by `a2wsgi` (#1825)
- Change default `--app-dir` from "." (dot) to "" (empty string) (#1835)

### Fixed

- Send code 1012 on shutdown for WebSockets (#1816)
- Use `surrogateescape` to encode headers on `websockets` implementation (#1005)
- Fix warning message on reload failure (#1784)

## 0.20.0 (2022-11-20)

### Added

- Check if handshake is completed before sending frame on `wsproto` shutdown (#1737)
- Add default headers to WebSockets implementations (#1606 & #1747)
- Warn user when `reload` and `workers` flag are used together (#1731)

### Fixed

- Use correct `WebSocket` error codes on `close` (#1753)
- Send disconnect event on connection lost for `wsproto` (#996)
- Add `SIGQUIT` handler to `UvicornWorker` (#1710)
- Fix crash on exist with "--uds" if socket doesn't exist (#1725)
- Annotate `CONFIG_KWARGS` in `UvicornWorker` class (#1746)

### Removed

- Remove conditional on `RemoteProtocolError.event_hint` on `wsproto` (#1486)
- Remove unused `handle_no_connect` on `wsproto` implementation (#1759)

## 0.19.0 (2022-10-19)

### Added

- Support Python 3.11 (#1652)
- Bump minimal `httptools` version to `0.5.0` (#1645)
- Ignore HTTP/2 upgrade and optionally ignore WebSocket upgrade (#1661)
- Add `py.typed` to comply with PEP 561 (#1687)

### Fixed

- Set `propagate` to `False` on "uvicorn" logger (#1288)
- USR1 signal is now handled correctly on `UvicornWorker`. (#1565)
- Use path with query string on `WebSockets` logs (#1385)
- Fix behavior on which "Date" headers were not updated on the same connection (#1706)

### Removed

- Remove the `--debug` flag (#1640)
- Remove the `DebugMiddleware` (#1697)

## 0.18.3 (2022-08-24)

### Fixed

- Remove cyclic references on HTTP implementations. (#1604)

### Changed

- `reload_delay` default changed from `None` to `0.25` on `uvicorn.run()` and `Config`. `None` is not an acceptable value anymore. (#1545)

## 0.18.2 (2022-06-27)

### Fixed

- Add default `log_config` on `uvicorn.run()` (#1541)
- Revert `logging` file name modification (#1543)

## 0.18.1 (2022-06-23)

### Fixed

- Use `DEFAULT_MAX_INCOMPLETE_EVENT_SIZE` as default to `h11_max_incomplete_event_size` on the CLI (#1534)

## 0.18.0 (2022-06-23)

### Added

- The `reload` flag prioritizes `watchfiles` instead of the deprecated `watchgod` (#1437)
- Annotate `uvicorn.run()` function (#1423)
- Allow configuring `max_incomplete_event_size` for `h11` implementation (#1514)

### Removed

- Remove `asgiref` dependency (#1532)

### Fixed

- Turn `raw_path` into bytes on both websockets implementations (#1487)
- Revert log exception traceback in case of invalid HTTP request (#1518)
- Set `asyncio.WindowsSelectorEventLoopPolicy()` when using multiple workers to avoid "WinError 87" (#1454)

## 0.17.6 (2022-03-11)

### Changed

- Change `httptools` range to `>=0.4.0` (#1400)

## 0.17.5 (2022-02-16)

### Fixed

- Fix case where url is fragmented in httptools protocol (#1263)
- Fix WSGI middleware not to explode quadratically in the case of a larger body (#1329)

### Changed

- Send HTTP 400 response for invalid request (#1352)

## 0.17.4 (2022-02-04)

### Fixed

- Replace `create_server` by `create_unix_server` (#1362)

## 0.17.3 (2022-02-03)

### Fixed

- Drop wsproto version checking. (#1359)

## 0.17.2 (2022-02-03)

### Fixed

- Revert #1332. While trying to solve the memory leak, it introduced an issue (#1345) when the server receives big chunks of data using the `httptools` implementation. (#1354)
- Revert stream interface changes. This was introduced on 0.14.0, and caused an issue (#1226), which caused a memory leak when sending TCP pings. (#1355)
- Fix wsproto version check expression (#1342)

## 0.17.1 (2022-01-28)

### Fixed

- Move all data handling logic to protocol and ensure connection is closed. (#1332)
- Change `spec_version` field from "2.1" to "2.3", as Uvicorn is compliant with that version of the ASGI specifications. (#1337)

## 0.17.0.post1 (2022-01-24)

### Fixed

- Add the `python_requires` version specifier (#1328)

## 0.17.0 (2022-01-14)

### Added

- Allow configurable websocket per-message-deflate setting (#1300)
- Support extra_headers for WS accept message (#1293)
- Add missing http version on websockets scope (#1309)

### Fixed/Removed

- Drop Python 3.6 support (#1261)
- Fix reload process behavior when exception is raised (#1313)
- Remove `root_path` from logs (#1294)

## 0.16.0 (2021-12-08)

### Added

- Enable read of uvicorn settings from environment variables (#1279)
- Bump `websockets` to 10.0. (#1180)
- Ensure non-zero exit code when startup fails (#1278)
- Increase `httptools` version range from "==0.2.*" to ">=0.2.0,<0.4.0". (#1243)
- Override default asyncio event loop with reload only on Windows (#1257)
- Replace `HttpToolsProtocol.pipeline` type from `list` to `deque`. (#1213)
- Replace `WSGIResponder.send_queue` type from `list` to `deque`. (#1214)

### Fixed

- Main process exit after startup failure on reloader classes (#1177)
- Add explicit casting on click options (#1217)
- Allow WebSocket close event to receive reason being None from ASGI app. (#1259)
- Fix a bug in `WebSocketProtocol.asgi_receive` on which we returned a close frame even if there were data messages before that frame in the read queue. (#1252)
- The option `--reload-dirs` was splitting a string into single character directories. (#1267)
- Only second SIGINT is able to forcefully shutdown the server (#1269)
- Allow app-dir parameter on the run() function (#1271)

## 0.15.0 (2021-08-13)

### Added

- Change reload to be configurable with glob patterns. Currently only `.py` files are watched, which is different from the previous default behavior. (#820)
- Add Python 3.10-rc.1 support. Now the server uses `asyncio.run` which will: start a fresh asyncio event loop, on shutdown cancel any background tasks rather than aborting them, `aexit` any remaining async generators, and shutdown the default `ThreadPoolExecutor`. (#1070)
- Exit with status 3 when worker starts failed (#1077)
- Add option to set websocket ping interval and timeout (#1048)
- Adapt bind_socket to make it usable with multiple processes (#1009)
- Add existence check to the reload directory(ies) (#1089)
- Add missing trace log for websocket protocols (#1083)
- Support disabling default Server and Date headers (#818)

### Changed

- Add PEP440 compliant version of click (#1099)
- Bump asgiref to 3.4.0 (#1100)

### Fixed

- When receiving a `SIGTERM` supervisors now terminate their processes before joining them (#1069)
- Fix the need of `httptools` on minimal installation (#1135)
- Fix ping parameters annotation in Config class (#1127)

## 0.14.0 (2021-06-01)

### Added

- Defaults ws max_size on server to 16MB (#995)
- Improve user feedback if no ws library installed (#926 and #1023)
- Support 'reason' field in 'websocket.close' messages (#957)
- Implemented lifespan.shutdown.failed (#755)

### Changed

- Upgraded websockets requirements (#1065)
- Switch to asyncio streams API (#869)
- Update httptools from 0.1.* to 0.2.* (#1024)
- Allow Click 8.0, refs #1016 (#1042)
- Add search for a trusted host in ProxyHeadersMiddleware (#591)
- Up wsproto to 1.0.0 (#892)

### Fixed

- Force reload_dirs to be a list (#978)
- Fix gunicorn worker not running if extras not installed (#901)
- Fix socket port 0 (#975)
- Prevent garbage collection of main lifespan task (#972)

## 0.13.4 (2021-02-20)

### Fixed

- Fixed wsgi middleware PATH_INFO encoding (#962)
- Fixed uvloop dependency  (#952) then (#959)
- Relax watchgod up bound (#946)
- Return 'connection: close' header in response (#721)

### Added

- Docs: Nginx + websockets (#948)
- Document the default value of 1 for workers (#940) (#943)
- Enabled permessage-deflate extension in websockets (#764)

## 0.13.3 (2020-12-29)

### Fixed

- Prevent swallowing of return codes from `subprocess` when running with Gunicorn by properly resetting signals. (#895)
- Tweak detection of app factories to be more robust. A warning is now logged when passing a factory without the `--factory` flag. (#914)
- Properly clean tasks when handshake is aborted when running with `--ws websockets`. (#921)

## 0.13.2 (2020-12-12)

### Fixed

- Log full exception traceback in case of invalid HTTP request. (#886 and #888)

## 0.13.1 (2020-12-12)

### Fixed

- Prevent exceptions when the ASGI application rejects a connection during the WebSocket handshake, when running on both `--ws wsproto` or `--ws websockets`. (#704 and #881)
- Ensure connection `scope` doesn't leak in logs when using JSON log formatters. (#859 and #884)

## 0.13.0 (2020-12-08)

### Added

- Add `--factory` flag to support factory-style application imports. (#875)
- Skip installation of signal handlers when not in the main thread. Allows using `Server` in multithreaded contexts without having to override `.install_signal_handlers()`. (#871)

## 0.12.3 (2020-11-21)

### Fixed
- Fix race condition that leads Quart to hang with uvicorn (#848)
- Use latin1 when decoding X-Forwarded-* headers (#701)
- Rework IPv6 support (#837)
- Cancel old keepalive-trigger before setting new one. (#832)

## 0.12.2 (2020-10-19)

### Added
- Adding ability to decrypt ssl key file (#808)
- Support .yml log config files (#799)
- Added python 3.9 support (#804)

### Fixed
- Fixes watchgod with common prefixes (#817)
- Fix reload with ipv6 host (#803)
- Added cli support for headers containing colon (#813)
- Sharing socket across workers on windows (#802)
- Note the need to configure trusted "ips" when using unix sockets (#796)

## 0.12.1 (2020-09-30)

### Changed
- Pinning h11 and python-dotenv to min versions (#789)
- Get docs/index.md in sync with README.md (#784)

### Fixed
- Improve changelog by pointing out breaking changes (#792)

## 0.12.0 (2020-09-28)

### Added
- Make reload delay configurable (#774)
- Upgrade maximum h11 dependency version to 0.10 (#772)
- Allow .json or .yaml --log-config files (#665)
- Add ASGI dict to the lifespan scope (#754)
- Upgrade wsproto to 0.15.0 (#750)
- Use optional package installs (#666)

### Changed
- Don't set log level for root logger (#767) 8/28/20 df81b168
- Uvicorn no longer ships extra dependencies `uvloop`, `websockets` and `httptools` as default.
  To install these dependencies use `uvicorn[standard]`.

### Fixed
- Revert "Improve shutdown robustness when using `--reload` or multiprocessing (#620)" (#756)
- Fix terminate error in windows (#744)
- Fix bug where --log-config disables uvicorn loggers (#512)

## 0.11.8 (2020-07-30)

* Fix a regression that caused Uvicorn to crash when using `--interface=wsgi`. (#730)
* Fix a regression that caused Uvicorn to crash when using unix domain sockets. (#729)

## 0.11.7 (2020-28-07)

* SECURITY FIX: Prevent sending invalid HTTP header names and values. (#725)
* SECURITY FIX: Ensure path value is escaped before logging to the console. (#724)
* Fix `--proxy-headers` client IP and host when using a Unix socket. (#636)

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
