## 0.14.0 - 2021-06-01

### Added

- Defaults ws max_size on server to 16MB ([#995](https://github.com/encode/uvicorn/pull/995/))
- Improve user feedback if no ws library installed ([#926](https://github.com/encode/uvicorn/pull/926/) and [#1023](https://github.com/encode/uvicorn/pull/1023/))
- Support `reason` field in 'websocket.close' messages ([#957](https://github.com/encode/uvicorn/pull/957/))
- Implement `lifespan.shutdown.failed` ([#755](https://github.com/encode/uvicorn/pull/755/))

### Changed

- Upgrade websockets requirements ([#1065](https://github.com/encode/uvicorn/pull/1065/))
- Switch to asyncio streams API ([#869](https://github.com/encode/uvicorn/pull/869/))
- Update httptools from 0.1.* to 0.2.* ([#1024](https://github.com/encode/uvicorn/pull/1024/))
- Allow Click 8.0, refs #1016 ([#1042](https://github.com/encode/uvicorn/pull/1042/))
- Add search for a trusted host in ProxyHeadersMiddleware ([#591](https://github.com/encode/uvicorn/pull/591))
- Upgrade wsproto to 1.0.0 ([#892](https://github.com/encode/uvicorn/pull/892/))

### Fixed

- Force `reload_dirs` to be a list ([#978](https://github.com/encode/uvicorn/pull/978/))
- Fix gunicorn worker not running if extras not installed ([#901](https://github.com/encode/uvicorn/pull/901/))
- Fix socket port 0 ([#975](https://github.com/encode/uvicorn/pull/975/))
- Prevent garbage collection of main lifespan task ([#972](https://github.com/encode/uvicorn/pull/972))

## 0.13.4 - 2021-02-20

### Fixed

- Fixed wsgi middleware PATH_INFO encoding ([#962](https://github.com/encode/uvicorn/pull/962/))
- Fixed uvloop dependency  ([#952](https://github.com/encode/uvicorn/pull/952/) and [#959](https://github.com/encode/uvicorn/pull/959/))
- Relax watchgod up bound ([#946](https://github.com/encode/uvicorn/pull/946/))
- Return 'connection: close' header in response ([#721](https://github.com/encode/uvicorn/pull/721/))

### Added

- Docs: Nginx + websockets ([#948](https://github.com/encode/uvicorn/pull/948/))
- Document the default value of 1 for workers ([#940](https://github.com/encode/uvicorn/pull/940/) and [#943](https://github.com/encode/uvicorn/pull/943/))
- Enabled permessage-deflate extension in websockets ([#764](https://github.com/encode/uvicorn/pull/764/))

## 0.13.3 - 2020-12-29

### Fixed

- Prevent swallowing of return codes from `subprocess` when running with Gunicorn by properly resetting signals. ([#895](https://github.com/encode/uvicorn/pull/895/))
- Tweak detection of app factories to be more robust. A warning is now logged when passing a factory without the `--factory` flag. ([#914](https://github.com/encode/uvicorn/pull/914/))
- Properly clean tasks when handshake is aborted when running with `--ws websockets`. ([#921](https://github.com/encode/uvicorn/pull/921/))

## 0.13.2 - 2020-12-12

### Fixed

- Log full exception traceback in case of invalid HTTP request. ([#886](https://github.com/encode/uvicorn/pull/886/) and [#888](https://github.com/encode/uvicorn/pull/888/))

## 0.13.1 - 2020-12-12

### Fixed

- Prevent exceptions when the ASGI application rejects a connection during the WebSocket handshake, when running on both `--ws wsproto` or `--ws websockets`. ([#704](https://github.com/encode/uvicorn/pull/704/) and [#881](https://github.com/encode/uvicorn/pull/881))
- Ensure connection `scope` doesn't leak in logs when using JSON log formatters. ([#859](https://github.com/encode/uvicorn/pull/859/) and [#884](https://github.com/encode/uvicorn/pull/884))

## 0.13.0 - 2020-12-08

### Added

- Add `--factory` flag to support factory-style application imports. ([#875](https://github.com/encode/uvicorn/pull/875/))
- Skip installation of signal handlers when not in the main thread. Allows using `Server` in multithreaded contexts without having to override `.install_signal_handlers()`. ([#871](https://github.com/encode/uvicorn/pull/871/))

## 0.12.3 - 2020-11-21

### Fixed
- Fix race condition that leads Quart to hang with uvicorn ([#848](https://github.com/encode/uvicorn/pull/848/))
- Use latin1 when decoding X-Forwarded-* headers ([#701](https://github.com/encode/uvicorn/pull/701/))
- Rework IPv6 support ([#837](https://github.com/encode/uvicorn/pull/837/))
- Cancel old keepalive-trigger before setting new one. ([#832](https://github.com/encode/uvicorn/pull/832/))

## 0.12.2 - 2020-10-19

### Added
- Adding ability to decrypt ssl key file ([#808](https://github.com/encode/uvicorn/pull/808/))
- Support .yml log config files ([#799](https://github.com/encode/uvicorn/pull/799/))
- Added python 3.9 support ([#804](https://github.com/encode/uvicorn/pull/804/))

### Fixed
- Fixes `watchgod` with common prefixes ([#817](https://github.com/encode/uvicorn/pull/817/))
- Fix reload with ipv6 host ([#803](https://github.com/encode/uvicorn/pull/803/))
- Add CLI support for headers containing colon ([#813](https://github.com/encode/uvicorn/pull/813/))
- Sharing socket across workers on windows ([#802](https://github.com/encode/uvicorn/pull/802/))
- Note the need to configure trusted "ips" when using unix sockets ([#796](https://github.com/encode/uvicorn/pull/796/))

## 0.12.1 - 2020-09-30

### Changed
- Pinning `h11` and `python-dotenv` to min versions ([#789](https://github.com/encode/uvicorn/pull/789/))
- Get docs/index.md in sync with README.md ([#784](https://github.com/encode/uvicorn/pull/784/))

### Fixed
- Improve changelog by pointing out breaking changes ([#792](https://github.com/encode/uvicorn/pull/792/))

## 0.12.0 - 2020-09-28

### Added
- Make reload delay configurable ([#774](https://github.com/encode/uvicorn/pull/774/))
- Upgrade maximum h11 dependency version to 0.10 ([#772](https://github.com/encode/uvicorn/pull/772/))
- Allow .json or .yaml --log-config files ([#665](https://github.com/encode/uvicorn/pull/665/))
- Add ASGI dict to the lifespan scope ([#754](https://github.com/encode/uvicorn/pull/754/))
- Upgrade wsproto to 0.15.0 ([#750](https://github.com/encode/uvicorn/pull/750/))
- Use optional package installs ([#666](https://github.com/encode/uvicorn/pull/666/))

### Changed
- Don't set log level for root logger ([#767](https://github.com/encode/uvicorn/pull/767/))
- Uvicorn no longer ships extra dependencies `uvloop`, `websockets` and
  `httptools` as default. To install these dependencies use
  `uvicorn[standard]`.

### Fixed
- Revert "Improve shutdown robustness when using `--reload` or multiprocessing (#620)" ([#756](https://github.com/encode/uvicorn/pull/756/))
- Fix terminate error in windows ([#744](https://github.com/encode/uvicorn/pull/744/))
- Fix bug where `--log-config` disables uvicorn loggers ([#512](https://github.com/encode/uvicorn/pull/512/))

## 0.11.8 - 2020-07-30

* Fix a regression that caused Uvicorn to crash when using `--interface=wsgi`. ([#730](https://github.com/encode/uvicorn/pull/730/))
* Fix a regression that caused Uvicorn to crash when using unix domain sockets. ([#729](https://github.com/encode/uvicorn/pull/729/))

## 0.11.7 - 2020-28-07

* SECURITY FIX: Prevent sending invalid HTTP header names and values. ([#725](https://github.com/encode/uvicorn/pull/725/))
* SECURITY FIX: Ensure path value is escaped before logging to the console. ([#724](https://github.com/encode/uvicorn/pull/724/))
* Fix `--proxy-headers` client IP and host when using a Unix socket. ([#636](https://github.com/encode/uvicorn/pull/636/))

## 0.11.6

* Fix overriding the root logger. ([#674](https://github.com/encode/uvicorn/pull/674))

## 0.11.5

* Revert "Watch all files, not just .py" due to unexpected side effects. ([#659](https://github.com/encode/uvicorn/pull/659/))
* Revert "Pass through gunicorn timeout config." due to unexpected side effects. ([#659](https://github.com/encode/uvicorn/pull/658/))

## 0.11.4

* Use `watchgod`, if installed, for watching code changes. ([#609](https://github.com/encode/uvicorn/pull/609/))
* Watch all files, not just .py. ([#646](https://github.com/encode/uvicorn/pull/646/))
* Pass through gunicorn timeout config. ([#631](https://github.com/encode/uvicorn/pull/631/))

## 0.11.3

* Update dependencies. ([#570](https://github.com/encode/uvicorn/pull/570/))

## 0.11.2

* Don't open socket until after application startup. ([#498](https://github.com/encode/uvicorn/pull/498/))
* Support `--backlog`. ([#545](https://github.com/encode/uvicorn/pull/545/))

## 0.11.1

* Use a more liberal `h11` dependency. Either `0.8.*` or `0.9.*`. ([#537](https://github.com/encode/uvicorn/pull/537/))

## 0.11.0

* Fix reload/multiprocessing on Windows with Python 3.8. ([#532](https://github.com/encode/uvicorn/pull/532/))
* Drop IOCP support. (Required for fix above.) ([#535](https://github.com/encode/uvicorn/pull/535/))
* Add `uvicorn --version` flag. ([#518](https://github.com/encode/uvicorn/pull/518/))
* Add `--use-colors` and `--no-use-colors` flags. ([#502](https://github.com/encode/uvicorn/pull/502/) and [#520](https://github.com/encode/uvicorn/pull/520/))
* Display port correctly, when auto port selection is used with `--port=0`. ([#531](https://github.com/encode/uvicorn/pull/531/))

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
