# Release Notes

## 0.20.0 - 2022-11-20

### Added

- Check if handshake is completed before sending frame on `wsproto` shutdown [#1737](https://github.com/encode/uvicorn/pull/1737)
- Add default headers to WebSockets implementations [#1606](https://github.com/encode/uvicorn/pull/1606) & [#1747](https://github.com/encode/uvicorn/pull/1747)
- Warn user when `reload` and `workers` flag are used together [#1731](https://github.com/encode/uvicorn/pull/1731)

### Fixed

- Use correct `WebSocket` error codes on `close` [#1753](https://github.com/encode/uvicorn/pull/1753)
- Send disconnect event on connection lost for `wsproto` [#996](https://github.com/encode/uvicorn/pull/996)
- Add `SIGQUIT` handler to `UvicornWorker` [#1710](https://github.com/encode/uvicorn/pull/1710)
- Fix crash on exist with "--uds" if socket doesn't exist [#1725](https://github.com/encode/uvicorn/pull/1725)
- Annotate `CONFIG_KWARGS` in `UvicornWorker` class [#1746](https://github.com/encode/uvicorn/pull/1746)

### Removed

- Remove conditional on `RemoteProtocolError.event_hint` on `wsproto` [#1486](https://github.com/encode/uvicorn/pull/1486)
- Remove unused `handle_no_connect` on `wsproto` implementation [#1759](https://github.com/encode/uvicorn/pull/1759)

## 0.19.0 - 2022-10-19

### Added

- Support Python 3.11 [#1652](https://github.com/encode/uvicorn/pull/1652)
- Bump minimal `httptools` version to `0.5.0` [#1645](https://github.com/encode/uvicorn/pull/1645)
- Ignore HTTP/2 upgrade and optionally ignore WebSocket upgrade [#1661](https://github.com/encode/uvicorn/pull/1661)
- Add `py.typed` to comply with PEP 561 [#1687](https://github.com/encode/uvicorn/pull/1687)

### Fixed

- Set `propagate` to `False` on "uvicorn" logger [#1288](https://github.com/encode/uvicorn/pull/1288)
- USR1 signal is now handled correctly on `UvicornWorker` [#1565](https://github.com/encode/uvicorn/pull/1565)
- Use path with query string on `WebSockets` logs [#1385](https://github.com/encode/uvicorn/pull/1385)
- Fix behavior on which "Date" headers were not updated on the same connection [#1706](https://github.com/encode/uvicorn/pull/1706)

### Removed

- Remove the `--debug` flag [#1640](https://github.com/encode/uvicorn/pull/1640)
- Remove the `DebugMiddleware` [#1697](https://github.com/encode/uvicorn/pull/1697)

## 0.18.3 - 2022-08-24

### Fixed

- Remove cyclic references on HTTP implementations [#1604](https://github.com/encode/uvicorn/pull/1604)

### Changed

- `reload_delay` default changed from `None` to `0.25` on `uvicorn.run()` and `Config`. `None` is not an acceptable value anymore [#1545](https://github.com/encode/uvicorn/pull/1545)

## 0.18.2 - 2022-06-27

### Fixed

- Add default `log_config` on `uvicorn.run()` [#1541](https://github.com/encode/uvicorn/pull/1541)
- Revert `logging` file name modification [#1543](https://github.com/encode/uvicorn/pull/1543)

## 0.18.1 - 2022-06-23

### Fixed

- Use `DEFAULT_MAX_INCOMPLETE_EVENT_SIZE` as default to `h11_max_incomplete_event_size` on the CLI [#1534](https://github.com/encode/uvicorn/pull/1534)

## 0.18.0 - 2022-06-23

### Added

- The `reload` flag prioritizes `watchfiles` instead of the deprecated `watchgod` [#1437](https://github.com/encode/uvicorn/pull/1437)
- Annotate `uvicorn.run()` function [#1423](https://github.com/encode/uvicorn/pull/1423)
- Allow configuring `max_incomplete_event_size` for `h11` implementation [#1514](https://github.com/encode/uvicorn/pull/1514)

### Removed

- Remove `asgiref` dependency [#1532](https://github.com/encode/uvicorn/pull/1532)

### Fixed

- Turn `raw_path` into bytes on both WebSocket implementations [#1487](https://github.com/encode/uvicorn/pull/1487)
- Revert log exception traceback in case of invalid HTTP request [#1518](https://github.com/encode/uvicorn/pull/1518)
- Set `asyncio.WindowsSelectorEventLoopPolicy()` when using multiple workers to avoid "WinError 87" [#1454](https://github.com/encode/uvicorn/pull/1454)

## 0.17.6 - 2022-03-11

### Changed

- Change `httptools` range to `>=0.4.0` [#1400](https://github.com/encode/uvicorn/pull/1400)

## 0.17.5 - 2022-02-16

### Fixed

- Fix case where url is fragmented in `httptools` protocol [#1263](https://github.com/encode/uvicorn/pull/1263)
- Fix WSGI middleware not to explode quadratically in the case of a larger body [#1329](https://github.com/encode/uvicorn/pull/1329)

### Changed

- Send HTTP 400 response for invalid request [#1352](https://github.com/encode/uvicorn/pull/1352)

## 0.17.4 - 2022-02-04

### Fixed

- Replace `create_server` by `create_unix_server` [#1362](https://github.com/encode/uvicorn/pull/1362)

## 0.17.3 - 2022-02-03

### Fixed

- Drop wsproto version checking [#1359](https://github.com/encode/uvicorn/pull/1359)

## 0.17.2 - 2022-02-03

### Fixed

- Revert [#1332](https://github.com/encode/uvicorn/pull/1332). While trying to solve the memory leak, it introduced an issue [#1345](https://github.com/encode/uvicorn/pull/1345) when the server receives big chunks of data using the `httptools` implementation [#1354](https://github.com/encode/uvicorn/pull/1354)
- Revert stream interface changes. This was introduced on 0.14.0, and caused an issue [#1226](https://github.com/encode/uvicorn/pull/1226), which caused a memory leak when sending TCP pings [#1355](https://github.com/encode/uvicorn/pull/1355)
- Fix wsproto version check expression [#1342](https://github.com/encode/uvicorn/pull/1342)

## 0.17.1 - 2022-01-28

### Fixed

- Move all data handling logic to protocol and ensure connection is closed [#1332](https://github.com/encode/uvicorn/pull/1332)
- Change `spec_version` field from "2.1" to "2.3", as Uvicorn is compliant with that version of the ASGI specifications [#1337](https://github.com/encode/uvicorn/pull/1337)

## 0.17.0.post1 - 2022-01-24

### Fixed

- Add the `python_requires` version specifier [#1328](https://github.com/encode/uvicorn/pull/1328)

## 0.17.0 - 2022-01-14

### Added

- Allow configurable websocket per-message-deflate setting [#1300](https://github.com/encode/uvicorn/pull/1300)
- Support extra_headers for WS accept message [#1293](https://github.com/encode/uvicorn/pull/1293)
- Add missing http version on WebSocket scope [#1309](https://github.com/encode/uvicorn/pull/1309)

### Fixed/Removed

- Drop Python 3.6 support [#1261](https://github.com/encode/uvicorn/pull/1261)
- Fix reload process behavior when exception is raised [#1313](https://github.com/encode/uvicorn/pull/1313)
- Remove `root_path` from logs [#1294](https://github.com/encode/uvicorn/pull/1294)

## 0.16.0 - 2021-12-08

### Added

- Enable read of uvicorn settings from environment variables [#1279](https://github.com/encode/uvicorn/pull/1279)
- Bump `websockets` to 10.0 [#1180](https://github.com/encode/uvicorn/pull/1180)
- Ensure non-zero exit code when startup fails [#1278](https://github.com/encode/uvicorn/pull/1278)
- Increase `httptools` version range from "==0.2.*" to ">=0.2.0,<0.4.0" [#1243](https://github.com/encode/uvicorn/pull/1243)
- Override default asyncio event loop with reload only on Windows [#1257](https://github.com/encode/uvicorn/pull/1257)
- Replace `HttpToolsProtocol.pipeline` type from `list` to `deque` [#1213](https://github.com/encode/uvicorn/pull/1213)
- Replace `WSGIResponder.send_queue` type from `list` to `deque` [#1214](https://github.com/encode/uvicorn/pull/1214)

### Fixed

- Main process exit after startup failure on reloader classes [#1177](https://github.com/encode/uvicorn/pull/1177)
- Add explicit casting on click options [#1217](https://github.com/encode/uvicorn/pull/1217)
- Allow WebSocket close event to receive reason being None from ASGI app [#1259](https://github.com/encode/uvicorn/pull/1259)
- Fix a bug in `WebSocketProtocol.asgi_receive` on which we returned a close frame even if there were data messages before that frame in the read queue [#1252](https://github.com/encode/uvicorn/pull/1252)
- The option `--reload-dirs` was splitting a string into single character directories [#1267](https://github.com/encode/uvicorn/pull/1267)
- Only second SIGINT is able to forcefully shutdown the server [#1269](https://github.com/encode/uvicorn/pull/1269)
- Allow `app-dir` parameter on the run() function [#1271](https://github.com/encode/uvicorn/pull/1271)


## 0.15.0 - 2021-08-13

### Added

- Change reload to be configurable with glob patterns. Currently only `.py` files are watched, which is different from the previous default behavior [#820](https://github.com/encode/uvicorn/pull/820)
- Add Python 3.10-rc.1 support. Now the server uses `asyncio.run` which will: start a fresh asyncio event loop, on shutdown cancel any background tasks rather than aborting them, `aexit` any remaining async generators, and shutdown the default `ThreadPoolExecutor` [#1070](https://github.com/encode/uvicorn/pull/1070)
- Exit with status 3 when worker starts failed [#1077](https://github.com/encode/uvicorn/pull/1077)
- Add option to set websocket ping interval and timeout [#1048](https://github.com/encode/uvicorn/pull/1048)
- Adapt bind_socket to make it usable with multiple processes [#1009](https://github.com/encode/uvicorn/pull/1009)
- Add existence check to the reload directory(ies) [#1089](https://github.com/encode/uvicorn/pull/1089)
- Add missing trace log for websocket protocols [#1083](https://github.com/encode/uvicorn/pull/1083)
- Support disabling default Server and Date headers [#818](https://github.com/encode/uvicorn/pull/818)

### Changed

- Add PEP440 compliant version of click [#1099](https://github.com/encode/uvicorn/pull/1099)
- Bump asgiref to 3.4.0 [#1100](https://github.com/encode/uvicorn/pull/1100)

### Fixed

- When receiving a `SIGTERM` supervisors now terminate their processes before joining them [#1069](https://github.com/encode/uvicorn/pull/1069)
- Fix the need of `httptools` on minimal installation [#1135](https://github.com/encode/uvicorn/pull/1135)
- Fix ping parameters annotation in Config class [#1127](https://github.com/encode/uvicorn/pull/1127)

## 0.14.0 - 2021-06-01

### Added

- Defaults ws max_size on server to 16MB [#995](https://github.com/encode/uvicorn/pull/995)
- Improve user feedback if no ws library installed [#926](https://github.com/encode/uvicorn/pull/926) and [#1023](https://github.com/encode/uvicorn/pull/1023)
- Support 'reason' field in 'websocket.close' messages [#957](https://github.com/encode/uvicorn/pull/957)
- Implemented lifespan.shutdown.failed [#755](https://github.com/encode/uvicorn/pull/755)

### Changed

- Upgraded websockets requirements [#1065](https://github.com/encode/uvicorn/pull/1065)
- Switch to asyncio streams API [#869](https://github.com/encode/uvicorn/pull/869)
- Update httptools from 0.1.* to 0.2.* [#1024](https://github.com/encode/uvicorn/pull/1024)
- Allow Click 8.0, refs #1016 [#1042](https://github.com/encode/uvicorn/pull/1042)
- Add search for a trusted host in `ProxyHeadersMiddleware` [#591](https://github.com/encode/uvicorn/pull/591)
- Bump `wsproto` to 1.0.0 [#892](https://github.com/encode/uvicorn/pull/892)

### Fixed

- Force `reload_dirs` to be a list [#978](https://github.com/encode/uvicorn/pull/978)
- Fix gunicorn worker not running if extras not installed [#901](https://github.com/encode/uvicorn/pull/901)
- Fix socket port 0 [#975](https://github.com/encode/uvicorn/pull/975)
- Prevent garbage collection of main lifespan task [#972](https://github.com/encode/uvicorn/pull/972)

## 0.13.4 - 2021-02-20

### Fixed

- Fixed wsgi middleware PATH_INFO encoding [#962](https://github.com/encode/uvicorn/pull/962)
- Fixed uvloop dependency  (#952) 2/10/21 then [#959](https://github.com/encode/uvicorn/pull/959)
- Relax watchgod up bound [#946](https://github.com/encode/uvicorn/pull/946)
- Return 'connection: close' header in response [#721](https://github.com/encode/uvicorn/pull/721)

### Added:

- Docs: Nginx + websockets [#948](https://github.com/encode/uvicorn/pull/948)
- Document the default value of 1 for workers (#940) [#943](https://github.com/encode/uvicorn/pull/943)
- Enabled permessage-deflate extension in websockets [#764](https://github.com/encode/uvicorn/pull/764)

## 0.13.3 - 2020-12-29

### Fixed

- Prevent swallowing of return codes from `subprocess` when running with Gunicorn by properly resetting signals. [#895](https://github.com/encode/uvicorn/pull/895)
- Tweak detection of app factories to be more robust. A warning is now logged when passing a factory without the `--factory` flag. [#914](https://github.com/encode/uvicorn/pull/914)
- Properly clean tasks when handshake is aborted when running with `--ws websockets`. [#921](https://github.com/encode/uvicorn/pull/921)

## 0.13.2 - 2020-12-12

### Fixed

- Log full exception traceback in case of invalid HTTP request [#886](https://github.com/encode/uvicorn/pull/886) and [#888](https://github.com/encode/uvicorn/pull/888)

## 0.13.1 - 2020-12-12

### Fixed

- Prevent exceptions when the ASGI application rejects a connection during the WebSocket handshake, when running on both `--ws wsproto` or `--ws websockets` [#704](https://github.com/encode/uvicorn/pull/704) and [#881](https://github.com/encode/uvicorn/pull/881)
- Ensure connection `scope` doesn't leak in logs when using JSON log formatters [#859](https://github.com/encode/uvicorn/pull/859) and [#884](https://github.com/encode/uvicorn/pull/884)

## 0.13.0 - 2020-12-08

### Added

- Add `--factory` flag to support factory-style application imports [#875](https://github.com/encode/uvicorn/pull/875)
- Skip installation of signal handlers when not in the main thread. Allows using `Server` in multithreaded contexts without having to override `.install_signal_handlers()` [#871](https://github.com/encode/uvicorn/pull/871)

## 0.12.3 - 2020-11-21

### Fixed
- Fix race condition that leads Quart to hang with uvicorn [#848](https://github.com/encode/uvicorn/pull/848)
- Use latin1 when decoding X-Forwarded-* headers [#701](https://github.com/encode/uvicorn/pull/701)
- Rework IPv6 support [#837](https://github.com/encode/uvicorn/pull/837)
- Cancel old keepalive-trigger before setting new one [#832](https://github.com/encode/uvicorn/pull/832)

## 0.12.2 - 2020-10-19

### Added
- Adding ability to decrypt ssl key file [#808](https://github.com/encode/uvicorn/pull/808)
- Support .yml log config files [#799](https://github.com/encode/uvicorn/pull/799)
- Added python 3.9 support [#804](https://github.com/encode/uvicorn/pull/804)

### Fixed
- Fixes `watchgod` with common prefixes [#817](https://github.com/encode/uvicorn/pull/817)
- Fix reload with ipv6 host [#803](https://github.com/encode/uvicorn/pull/803)
- Added cli support for headers containing colon [#813](https://github.com/encode/uvicorn/pull/813)
- Sharing socket across workers on windows [#802](https://github.com/encode/uvicorn/pull/802)
- Note the need to configure trusted "ips" when using unix sockets [#796](https://github.com/encode/uvicorn/pull/796)

## 0.12.1 - 2020-09-30

### Changed
- Pinning h11 and python-dotenv to min versions [#789](https://github.com/encode/uvicorn/pull/789)
- Get docs/index.md in sync with README.md [#784](https://github.com/encode/uvicorn/pull/784)

### Fixed
- Improve changelog by pointing out breaking changes [#792](https://github.com/encode/uvicorn/pull/792)

## 0.12.0 - 2020-09-28

### Added
- Make reload delay configurable [#774](https://github.com/encode/uvicorn/pull/774)
- Upgrade maximum h11 dependency version to 0.10 [#772](https://github.com/encode/uvicorn/pull/772)
- Allow .json or .yaml --log-config files [#665](https://github.com/encode/uvicorn/pull/665)
- Add ASGI dict to the lifespan scope [#754](https://github.com/encode/uvicorn/pull/754)
- Upgrade wsproto to 0.15.0 [#750](https://github.com/encode/uvicorn/pull/750)
- Use optional package installs [#666](https://github.com/encode/uvicorn/pull/666)

### Changed
- Dont set log level for root logger [#767](https://github.com/encode/uvicorn/pull/767)
- Uvicorn no longer ships extra dependencies `uvloop`, `websockets` and
  `httptools` as default. To install these dependencies use
  `uvicorn[standard]`.

### Fixed
- Revert "Improve shutdown robustness when using `--reload` or multiprocessing [#620](https://github.com/encode/uvicorn/pull/620)" [#756](https://github.com/encode/uvicorn/pull/756)
- Fix terminate error in windows [#744](https://github.com/encode/uvicorn/pull/744)
- Fix bug where --log-config disables uvicorn loggers [#512](https://github.com/encode/uvicorn/pull/512)

## 0.11.8 - 2020-07-30

* Fix a regression that caused Uvicorn to crash when using `--interface=wsgi` [#730](https://github.com/encode/uvicorn/pull/730)
* Fix a regression that caused Uvicorn to crash when using unix domain sockets [#729](https://github.com/encode/uvicorn/pull/729)

## 0.11.7 - 2020-28-07

* SECURITY FIX: Prevent sending invalid HTTP header names and values [#725](https://github.com/encode/uvicorn/pull/725)
* SECURITY FIX: Ensure path value is escaped before logging to the console [#724](https://github.com/encode/uvicorn/pull/724)
* Fix `--proxy-headers` client IP and host when using a Unix socket [#636](https://github.com/encode/uvicorn/pull/636)

## 0.11.6

* Fix overriding the root logger

## 0.11.5

* Revert "Watch all files, not just .py" due to unexpected side effects
* Revert "Pass through gunicorn timeout config." due to unexpected side effects

## 0.11.4

* Use `watchgod`, if installed, for watching code changes
* Watch all files, not just .py
* Pass through gunicorn timeout config

## 0.11.3

* Update dependencies

## 0.11.2

* Don't open socket until after application startup
* Support `--backlog`

## 0.11.1

* Use a more liberal `h11` dependency. Either `0.8.*` or `0.9.*``

## 0.11.0

* Fix reload/multiprocessing on Windows with Python 3.8
* Drop IOCP support. (Required for fix above.)
* Add `uvicorn --version` flag
* Add `--use-colors` and `--no-use-colors` flags
* Display port correctly, when auto port selection isused with `--port=0`

## 0.10.8

* Fix reload/multiprocessing error

## 0.10.7

* Use resource_sharer.DupSocket to resolve socket sharing on Windows

## 0.10.6

* Exit if `workers` or `reload` are use without an app import string style
* Reorganise supervisor processes to properly hand over sockets on windows

## 0.10.5

* Update uvloop dependency to 0.14+

## 0.10.4

* Error clearly when `workers=<NUM>` is used with app instance, instead of an app import string
* Switch `--reload-dir` to current working directory by default

## 0.10.3

* Add ``--log-level trace``

## 0.10.2

* Enable --proxy-headers by default

## 0.10.1

* Resolve issues with logging when using `--reload` or `--workers`
* Setup up root logger to capture output for all logger instances, not just `uvicorn.error` and `uvicorn.access`

## 0.10.0

* Support for Python 3.8
* Separated out `uvicorn.error` and `uvicorn.access` logs
* Coloured log output when connected to a terminal
* Dropped `logger=` config setting
* Added `--log-config [FILE]` and `log_config=[str|dict]`. May either be a Python logging config dictionary or the file name of a logging configuration
* Added `--forwarded_allow_ips` and `forwarded_allow_ips`. Defaults to the value of the `$FORWARDED_ALLOW_IPS` environment variable or "127.0.0.1". The `--proxy-headers` flag now defaults to `True`, but only trusted IPs are used to populate forwarding info
* The `--workers` setting now defaults to the value of the `$WEB_CONCURRENCY` environment variable
* Added support for `--env-file`. Requires `python-dotenv`
