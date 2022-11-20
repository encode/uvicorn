# Change Log

## 0.20.0 - 2022-11-20

### Added

- Check if handshake is completed before sending frame on `wsproto` shutdown (#1737)
- Add default headers to WebSockets implementations (#1606 & #1747) 28/10/22
- Warn user when `reload` and `workers` flag are used together (#1731) 31/10/22

### Fixed

- Use correct `WebSocket` error codes on `close` (#1753) 20/11/22
- Send disconnect event on connection lost for `wsproto` (#996) 29/10/22
- Add `SIGQUIT` handler to `UvicornWorker` (#1710) 01/11/22
- Fix crash on exist with "--uds" if socket doesn't exist (#1725) 27/10/22
- Annotate `CONFIG_KWARGS` in `UvicornWorker` class (#1746) 31/10/22

### Removed

- Remove conditional on `RemoteProtocolError.event_hint` on `wsproto` (#1486) 31/10/22
- Remove unused `handle_no_connect` on `wsproto` implementation (#1759) 17/11/22

## 0.19.0 - 2022-10-19

### Added

- Support Python 3.11 (#1652) 16/09/22
- Bump minimal `httptools` version to `0.5.0` (#1645) 13/09/22
- Ignore HTTP/2 upgrade and optionally ignore WebSocket upgrade (#1661) 19/10/22
- Add `py.typed` to comply with PEP 561 (#1687) 07/10/22

### Fixed

- Set `propagate` to `False` on "uvicorn" logger (#1288) 08/10/22
- USR1 signal is now handled correctly on `UvicornWorker`. (#1565) 26/08/22
- Use path with query string on `WebSockets` logs (#1385) 11/09/22
- Fix behavior on which "Date" headers were not updated on the same connection (#1706) 19/10/22

### Removed

- Remove the `--debug` flag (#1640) 14/09/22
- Remove the `DebugMiddleware` (#1697) 07/10/22

## 0.18.3 - 2022-08-24

### Fixed

- Remove cyclic references on HTTP implementations. (#1604) 24/08/22

### Changed

- `reload_delay` default changed from `None` to `0.25` on `uvicorn.run()` and `Config`. `None` is not an acceptable value anymore. (#1545) 02/07/22

## 0.18.2 - 2022-06-27

### Fixed

- Add default `log_config` on `uvicorn.run()` (#1541) 24/06/22
- Revert `logging` file name modification (#1543) 27/06/22

## 0.18.1 - 2022-06-23

### Fixed

- Use `DEFAULT_MAX_INCOMPLETE_EVENT_SIZE` as default to `h11_max_incomplete_event_size` on the CLI (#1534) 23/06/22

## 0.18.0 - 2022-06-23

### Added

- The `reload` flag prioritizes `watchfiles` instead of the deprecated `watchgod` (#1437) 18/06/22
- Annotate `uvicorn.run()` function (#1423) 10/05/22
- Allow configuring `max_incomplete_event_size` for `h11` implementation (#1514) 22/06/22

### Removed

- Remove `asgiref` dependency (#1532) 22/06/22

### Fixed

- Turn `raw_path` into bytes on both websockets implementations (#1487) 16/05/22
- Revert log exception traceback in case of invalid HTTP request (#1518) 14/06/22
- Set `asyncio.WindowsSelectorEventLoopPolicy()` when using multiple workers to avoid "WinError 87" (#1454) 22/06/22

## 0.17.6 - 2022-03-11

### Changed

- Change `httptools` range to `>=0.4.0` (#1400) 11/03/22

## 0.17.5 - 2022-02-16

### Fixed

- Fix case where url is fragmented in httptools protocol (#1263) 16/02/22
- Fix WSGI middleware not to explode quadratically in the case of a larger body (#1329) 16/02/16

### Changed

- Send HTTP 400 response for invalid request (#1352) 2/11/22

## 0.17.4 - 2022-02-04

### Fixed

- Replace `create_server` by `create_unix_server` (#1362) 04/02/22

## 0.17.3 - 2022-02-03

### Fixed

- Drop wsproto version checking. (#1359) 03/02/22

## 0.17.2 - 2022-02-03

### Fixed

- Revert #1332. While trying to solve the memory leak, it introduced an issue (#1345) when the server receives big chunks of data using the `httptools` implementation. (#1354) 03/02/22
- Revert stream interface changes. This was introduced on 0.14.0, and caused an issue (#1226), which caused a memory leak when sending TCP pings. (#1355) 03/02/22
- Fix wsproto version check expression (#1342) 28/01/22

## 0.17.1 - 2022-01-28

### Fixed

- Move all data handling logic to protocol and ensure connection is closed. (#1332) 28/01/22
- Change `spec_version` field from "2.1" to "2.3", as Uvicorn is compliant with that version of the ASGI specifications. (#1337) 25/01/22

## 0.17.0.post1 - 2022-01-24

### Fixed

- Add the `python_requires` version specifier (#1328) 17/01/22

## 0.17.0 - 2022-01-14

### Added

- Allow configurable websocket per-message-deflate setting (#1300) 29/12/21
- Support extra_headers for WS accept message (#1293) 06/01/22
- Add missing http version on websockets scope (#1309) 08/01/22

### Fixed/Removed

- Drop Python 3.6 support (#1261) 06/01/22
- Fix reload process behavior when exception is raised (#1313) 11/01/22
- Remove `root_path` from logs (#1294) 25/12/21

## 0.16.0 - 2021-12-08

### Added

- Enable read of uvicorn settings from environment variables (#1279) 06/12/21
- Bump `websockets` to 10.0. (#1180) 13/09/21
- Ensure non-zero exit code when startup fails (#1278) 06/12/21
- Increase `httptools` version range from "==0.2.*" to ">=0.2.0,<0.4.0". (#1243) 8/11/21
- Override default asyncio event loop with reload only on Windows (#1257) 24/11/21
- Replace `HttpToolsProtocol.pipeline` type from `list` to `deque`. (#1213) 10/10/21
- Replace `WSGIResponder.send_queue` type from `list` to `deque`. (#1214) 10/10/21

### Fixed

- Main process exit after startup failure on reloader classes (#1177) 30/09/21
- Add explicit casting on click options (#1217) 11/10/21
- Allow WebSocket close event to receive reason being None from ASGI app. (#1259) 23/11/21
- Fix a bug in `WebSocketProtocol.asgi_receive` on which we returned a close frame even if there were data messages before that frame in the read queue. (#1252) 25/11/21
- The option `--reload-dirs` was splitting a string into single character directories. (#1267) 25/11/21
- Only second SIGINT is able to forcefully shutdown the server (#1269) 28/11/21
- Allow app-dir parameter on the run() function (#1271) 06/12/21


## 0.15.0 - 2021-08-13

### Added

- Change reload to be configurable with glob patterns. Currently only `.py` files are watched, which is different from the previous default behavior. (#820) 08/08/21
- Add Python 3.10-rc.1 support. Now the server uses `asyncio.run` which will: start a fresh asyncio event loop, on shutdown cancel any background tasks rather than aborting them, `aexit` any remaining async generators, and shutdown the default `ThreadPoolExecutor`. (#1070) 30/07/21
- Exit with status 3 when worker starts failed (#1077) 22/06/21
- Add option to set websocket ping interval and timeout (#1048) 09/06/21
- Adapt bind_socket to make it usable with multiple processes (#1009) 21/06/21
- Add existence check to the reload directory(ies) (#1089) 21/06/21
- Add missing trace log for websocket protocols (#1083) 19/06/21
- Support disabling default Server and Date headers (#818) 11/06/21

### Changed

- Add PEP440 compliant version of click (#1099) 29/06/21
- Bump asgiref to 3.4.0 (#1100) 29/06/21

### Fixed

- When receiving a `SIGTERM` supervisors now terminate their processes before joining them (#1069) 30/07/21
- Fix the need of `httptools` on minimal installation (#1135) 30/07/21
- Fix ping parameters annotation in Config class (#1127) 19/07/21

## 0.14.0 - 2021-06-01

### Added

- Defaults ws max_size on server to 16MB (#995) 5/29/21
- Improve user feedback if no ws library installed (#926 and #1023) 2/27/21
- Support 'reason' field in 'websocket.close' messages (#957) 2/24/21
- Implemented lifespan.shutdown.failed (#755) 2/25/21

### Changed

- Upgraded websockets requirements (#1065)  6/1/21
- Switch to asyncio streams API (#869) 5/29/21
- Update httptools from 0.1.* to 0.2.* (#1024) 5/28/21
- Allow Click 8.0, refs #1016 (#1042) 5/23/21
- Add search for a trusted host in ProxyHeadersMiddleware (#591) 3/13/21
- Up wsproto to 1.0.0 (#892) 2/25/21

### Fixed

- Force reload_dirs to be a list (#978) 6/1/21
- Fix gunicorn worker not running if extras not installed (#901) 5/28/21
- Fix socket port 0 (#975) 3/5/21
- Prevent garbage collection of main lifespan task (#972) 3/4/21

## 0.13.4 - 2021-02-20

### Fixed

- Fixed wsgi middleware PATH_INFO encoding (#962) 2/20/21
- Fixed uvloop dependency  (#952) 2/10/21 then (#959) 2/20/21
- Relax watchgod up bound (#946) 1/31/21
- Return 'connection: close' header in response (#721) 1/25/21

### Added:

- Docs: Nginx + websockets (#948) 2/10/21
- Document the default value of 1 for workers (#940) (#943) 1/25/21
- Enabled permessage-deflate extension in websockets (#764) 1/1/21

## 0.13.3 - 2020-12-29

### Fixed

- Prevent swallowing of return codes from `subprocess` when running with Gunicorn by properly resetting signals. (Pull #895)
- Tweak detection of app factories to be more robust. A warning is now logged when passing a factory without the `--factory` flag. (Pull #914)
- Properly clean tasks when handshake is aborted when running with `--ws websockets`. (Pull #921)

## 0.13.2 - 2020-12-12

### Fixed

- Log full exception traceback in case of invalid HTTP request. (Pull #886 and #888)

## 0.13.1 - 2020-12-12

### Fixed

- Prevent exceptions when the ASGI application rejects a connection during the WebSocket handshake, when running on both `--ws wsproto` or `--ws websockets`. (Pull #704 and #881)
- Ensure connection `scope` doesn't leak in logs when using JSON log formatters. (Pull #859 and #884)

## 0.13.0 - 2020-12-08

### Added

- Add `--factory` flag to support factory-style application imports. (#875) 2020-12-07 50fc0d1c
- Skip installation of signal handlers when not in the main thread. Allows using `Server` in multithreaded contexts without having to override `.install_signal_handlers()`. (#871) 2020-12-07 ce2ef45a

## 0.12.3 - 2020-11-21

### Fixed
- Fix race condition that leads Quart to hang with uvicorn (#848) 11/18/20 de213614
- Use latin1 when decoding X-Forwarded-* headers (#701) 11/12/20 45e6e831
- Rework IPv6 support (#837) 11/8/20 bdab488e
- Cancel old keepalive-trigger before setting new one. (#832) 10/26/20 d5dcf80c

## 0.12.2 - 2020-10-19

### Added
- Adding ability to decrypt ssl key file (#808) 10/12/20 90dbb6e0
- Support .yml log config files (#799) 10/6/20 b468950e
- Added python 3.9 support (#804) 10/6/20 08fd0559

### Fixed
- Fixes watchgod with common prefixes (#817) 10/14/20 1b32f997
- Fix reload with ipv6 host (#803) 10/14/20 5acaee5b
- Added cli support for headers containing colon (#813) 10/12/20 68732899
- Sharing socket across workers on windows (#802) 10/12/20 103167a0
- Note the need to configure trusted "ips" when using unix sockets (#796) 10/4/20 a504c569

## 0.12.1 - 2020-09-30

### Changed
- Pinning h11 and python-dotenv to min versions (#789) 9/29/20 bbf19c66
- Get docs/index.md in sync with README.md (#784) 9/29/20 70ebcfdf

### Fixed
- Improve changelog by pointing out breaking changes (#792) 9/29/20 e2b75064

## 0.12.0 - 2020-09-28

### Added
- Make reload delay configurable (#774) 9/28/20 98010027
- Upgrade maximum h11 dependency version to 0.10 (#772) 8/28/20 54d729cc
- Allow .json or .yaml --log-config files (#665) 8/18/20 093a1f7c
- Add ASGI dict to the lifespan scope (#754) 8/15/20 8150c3eb
- Upgrade wsproto to 0.15.0 (#750) 8/13/20 fbce393f
- Use optional package installs (#666) 8/10/20 5fa99a11

### Changed
- Dont set log level for root logger (#767) 8/28/20 df81b168
- Uvicorn no longer ships extra dependencies `uvloop`, `websockets` and
  `httptools` as default. To install these dependencies use
  `uvicorn[standard]`.

### Fixed
- Revert "Improve shutdown robustness when using `--reload` or multiprocessing (#620)" (#756) 8/28/20 ff4af12d
- Fix terminate error in windows (#744) 8/27/20 dd3b842d
- Fix bug where --log-config disables uvicorn loggers (#512) 8/11/20 a9c37cc4

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
