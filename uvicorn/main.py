import logging
import platform
import ssl
import sys
from enum import Enum
from pathlib import Path
from typing import Iterable, List

from typer import Option, Typer, echo

import uvicorn
from uvicorn.config import (
    HTTP_PROTOCOLS,
    INTERFACES,
    LIFESPAN,
    LOG_LEVELS,
    LOGGING_CONFIG,
    LOOP_SETUPS,
    SSL_PROTOCOL_VERSION,
    WS_PROTOCOLS,
    Config,
)
from uvicorn.server import Server, ServerState  # noqa: F401  # Used to be defined here.
from uvicorn.supervisors import ChangeReload, Multiprocess


def _create_enum(name: str, iter: Iterable[str], *exclude: str) -> Enum:
    class StrEnum(str, Enum):
        pass

    return StrEnum(name, [(k, k) for k in iter if k not in exclude])


LogLevel = _create_enum("LogLevel", LOG_LEVELS.keys())
HttpProtocol = _create_enum("HttpProtocol", HTTP_PROTOCOLS.keys())
WsProtocol = _create_enum("WsProtocol", WS_PROTOCOLS.keys())
Lifespan = _create_enum("Lifespan", LIFESPAN.keys())
LoopSetup = _create_enum("LoopSetup", LOOP_SETUPS.keys(), "none")
AsgiInterface = _create_enum("AsgiInterface", INTERFACES)

logger = logging.getLogger("uvicorn.error")


def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    echo(
        "Running uvicorn %s with %s %s on %s"
        % (
            uvicorn.__version__,
            platform.python_implementation(),
            platform.python_version(),
            platform.system(),
        )
    )
    ctx.exit()


main = Typer(add_completion=False)


@main.command()
def command(
    app: str,
    host: str = Option("127.0.0.1", help="Bind socket to this host."),
    port: int = Option(8000, help="Bind socket to this port."),
    uds: str = Option(None, help="Bind to a UNIX domain socket."),
    fd: int = Option(None, help="Bind to socket from this file descriptor."),
    debug: bool = Option(False, help="Enable debug mode.", hidden=True),
    reload: bool = Option(
        False, "--reload", help="Enable auto-reload.", show_default=False
    ),
    reload_dirs: List[str] = Option(
        None,
        "--reload-dir",
        help=(
            "Set reload directories explicitly, instead of using the current "
            "working directory."
        ),
    ),
    reload_delay: float = Option(
        0.25, help="Delay between previous and next check if application needs to be."
    ),
    workers: int = Option(
        None,
        help=(
            "Number of worker processes. Defaults to the $WEB_CONCURRENCY environment "
            "variable if available, or 1. Not valid with --reload."
        ),
    ),
    loop: LoopSetup = Option(LoopSetup.auto, help="Event loop implementation."),
    http: HttpProtocol = Option(
        HttpProtocol.auto, help="HTTP protocol implementation."
    ),
    ws: WsProtocol = Option(WsProtocol.auto, help="WebSocket protocol implementation."),
    lifespan: Lifespan = Option(Lifespan.auto, help="Lifespan implementation."),
    interface: AsgiInterface = Option(
        AsgiInterface.auto,
        help="Select ASGI3, ASGI2, or WSGI as the application interface.",
    ),
    env_file: Path = Option(None, help="Environment configuration file.", exists=True),
    log_config: Path = Option(
        None,
        help="Logging configuration file. Supported formats: .ini, .json, .yaml.",
        exists=True,
    ),
    log_level: LogLevel = Option(LogLevel.info, help="Log level."),
    access_log: bool = Option(
        True, help="Enable/Disable access log.", show_default=False
    ),
    use_colors: bool = Option(None, help="Enable/Disable colorized logging."),
    proxy_headers: bool = Option(
        True,
        help=(
            "Enable/Disable X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to "
            "populate remote address info."
        ),
        show_default=False,
    ),
    forwarded_allow_ips: str = Option(
        None,
        help=(
            "Comma separated list of IPs to trust with proxy headers. Defaults to the "
            "$FORWARDED_ALLOW_IPS environment variable if available, or '127.0.0.1'."
        ),
    ),
    root_path: str = Option(
        "",
        help=(
            "Set the ASGI 'root_path' for applications submounted below a given URL "
            "path."
        ),
        show_default=False,
    ),
    limit_concurrency: int = Option(
        None,
        help=(
            "Maximum number of concurrent connections or tasks to allow, before"
            " issuing HTTP 503 responses."
        ),
    ),
    backlog: int = Option(
        2048,
        help="Maximum number of connections to hold in backlog.",
        show_default=False,
    ),
    limit_max_requests: int = Option(
        None,
        help="Maximum number of requests to service before terminating the process.",
    ),
    timeout_keep_alive: int = Option(
        5,
        help=(
            "Close Keep-Alive connections if no new data is received within this"
            " timeout."
        ),
    ),
    ssl_keyfile: str = Option(None, help="SSL key file."),
    ssl_certfile: str = Option(None, help="SSL certificate file."),
    ssl_keyfile_password: str = Option(None, help="SSL keyfile password."),
    ssl_version: int = Option(
        SSL_PROTOCOL_VERSION, help="SSL version to use (see stdlib ssl module's)."
    ),
    ssl_cert_reqs: int = Option(
        ssl.CERT_NONE,
        help="Whether client certificate is required (see stdlib ssl module's).",
    ),
    ssl_ca_certs: str = Option(None, help="CA certificates file."),
    ssl_ciphers: str = Option("TLSv1", help="Ciphers to use (see stdlib ssl module's)"),
    headers: List[str] = Option(
        None,
        "--header",
        help="Specify custom default HTTP response headers as a Name:Value pair",
    ),
    version: bool = Option(
        None,
        "--version",
        is_eager=True,
        expose_value=False,
        callback=print_version,
        is_flag=True,
        help="Display the uvicorn version and exit.",
    ),
    app_dir: str = Option(
        ".",
        help=(
            "Look for APP in the specified directory, by adding this to the PYTHONPATH."
            " Defaults to the current working directory."
        ),
    ),
    factory: bool = Option(
        False,
        "--factory",
        help="Treat APP as an application factory, i.e. a () -> <ASGI app> callable.",
    ),
):
    sys.path.insert(0, app_dir)

    kwargs = {
        "app": app,
        "host": host,
        "port": port,
        "uds": uds,
        "fd": fd,
        "loop": loop,
        "http": http,
        "ws": ws,
        "lifespan": lifespan,
        "env_file": env_file,
        "log_config": LOGGING_CONFIG if log_config is None else log_config,
        "log_level": log_level,
        "access_log": access_log,
        "interface": interface,
        "debug": debug,
        "reload": reload,
        "reload_dirs": reload_dirs,
        "reload_delay": reload_delay,
        "workers": workers,
        "proxy_headers": proxy_headers,
        "forwarded_allow_ips": forwarded_allow_ips,
        "root_path": root_path,
        "limit_concurrency": limit_concurrency,
        "backlog": backlog,
        "limit_max_requests": limit_max_requests,
        "timeout_keep_alive": timeout_keep_alive,
        "ssl_keyfile": ssl_keyfile,
        "ssl_certfile": ssl_certfile,
        "ssl_keyfile_password": ssl_keyfile_password,
        "ssl_version": ssl_version,
        "ssl_cert_reqs": ssl_cert_reqs,
        "ssl_ca_certs": ssl_ca_certs,
        "ssl_ciphers": ssl_ciphers,
        "headers": [header.split(":", 1) for header in headers],
        "use_colors": use_colors,
        "factory": factory,
    }
    run(**kwargs)


def run(app, **kwargs):
    config = Config(app, **kwargs)
    server = Server(config=config)

    if (config.reload or config.workers > 1) and not isinstance(app, str):
        logger = logging.getLogger("uvicorn.error")
        logger.warning(
            "You must pass the application as an import string to enable 'reload' or "
            "'workers'."
        )
        sys.exit(1)

    if config.should_reload:
        sock = config.bind_socket()
        supervisor = ChangeReload(config, target=server.run, sockets=[sock])
        supervisor.run()
    elif config.workers > 1:
        sock = config.bind_socket()
        supervisor = Multiprocess(config, target=server.run, sockets=[sock])
        supervisor.run()
    else:
        server.run()


if __name__ == "__main__":
    main()
