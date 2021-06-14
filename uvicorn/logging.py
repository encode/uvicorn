import http
import logging
import sys
import time
from collections import abc
from copy import copy
from os import getpid
from typing import Optional

import click

TRACE_LOG_LEVEL = 5


class ColourizedFormatter(logging.Formatter):
    """
    A custom log formatter class that:

    * Outputs the LOG_LEVEL with an appropriate color.
    * If a log call includes an `extras={"color_message": ...}` it will be used
      for formatting the output, instead of the plain text message.
    """

    level_name_colors = {
        TRACE_LOG_LEVEL: lambda level_name: click.style(str(level_name), fg="blue"),
        logging.DEBUG: lambda level_name: click.style(str(level_name), fg="cyan"),
        logging.INFO: lambda level_name: click.style(str(level_name), fg="green"),
        logging.WARNING: lambda level_name: click.style(str(level_name), fg="yellow"),
        logging.ERROR: lambda level_name: click.style(str(level_name), fg="red"),
        logging.CRITICAL: lambda level_name: click.style(
            str(level_name), fg="bright_red"
        ),
    }

    def __init__(
        self,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: str = "%",
        use_colors: Optional[bool] = None,
    ):
        if use_colors in (True, False):
            self.use_colors = use_colors
        else:
            self.use_colors = sys.stdout.isatty()
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)

    def color_level_name(self, level_name: str, level_no: int) -> str:
        def default(level_name: str) -> str:
            return str(level_name)  # pragma: no cover

        func = self.level_name_colors.get(level_no, default)
        return func(level_name)

    def should_use_colors(self) -> bool:
        return True  # pragma: no cover

    def formatMessage(self, record: logging.LogRecord) -> str:
        recordcopy = copy(record)
        levelname = recordcopy.levelname
        seperator = " " * (8 - len(recordcopy.levelname))
        if self.use_colors:
            levelname = self.color_level_name(levelname, recordcopy.levelno)
            if "color_message" in recordcopy.__dict__:
                recordcopy.msg = recordcopy.__dict__["color_message"]
                recordcopy.__dict__["message"] = recordcopy.getMessage()
        recordcopy.__dict__["levelprefix"] = levelname + ":" + seperator
        return super().formatMessage(recordcopy)


class DefaultFormatter(ColourizedFormatter):
    def should_use_colors(self) -> bool:
        return sys.stderr.isatty()  # pragma: no cover


class AccessFormatter(ColourizedFormatter):
    status_code_colours = {
        1: lambda code: click.style(str(code), fg="bright_white"),
        2: lambda code: click.style(str(code), fg="green"),
        3: lambda code: click.style(str(code), fg="yellow"),
        4: lambda code: click.style(str(code), fg="red"),
        5: lambda code: click.style(str(code), fg="bright_red"),
    }

    def get_status_code(self, status_code: int) -> str:
        try:
            status_phrase = http.HTTPStatus(status_code).phrase
        except ValueError:
            status_phrase = ""
        status_and_phrase = "%s %s" % (status_code, status_phrase)
        if self.use_colors:

            def default(code: int) -> str:
                return status_and_phrase  # pragma: no cover

            func = self.status_code_colours.get(status_code // 100, default)
            return func(status_and_phrase)
        return status_and_phrase

    def formatMessage(self, record: logging.LogRecord) -> str:
        recordcopy = copy(record)
        (
            client_addr,
            method,
            full_path,
            http_version,
            status_code,
        ) = recordcopy.args
        status_code = self.get_status_code(int(status_code))
        request_line = "%s %s HTTP/%s" % (method, full_path, http_version)
        if self.use_colors:
            request_line = click.style(request_line, bold=True)
        recordcopy.__dict__.update(
            {
                "client_addr": client_addr,
                "request_line": request_line,
                "status_code": status_code,
            }
        )
        return super().formatMessage(recordcopy)


class GunicornSafeAtoms(abc.Mapping):
    """Implement atoms necessary for gunicorn log.

    This class does a few things:
    - provide all atoms necessary for gunicorn log formatter
    - collect response body size for reporting from ASGI messages
    - provide mapping interface that returns '-' for missing atoms
    - escapes double quotes found in atom strings
    """

    def __init__(self, scope, timing):
        self.scope = scope
        self.timing = timing
        self.status_code = None
        self.response_headers = {}
        self.response_length = 0

        self._request_headers = None

    @property
    def request_headers(self):
        if self._request_headers is None:
            self._request_headers = {
                k.decode("ascii"): v.decode("ascii") for k, v in self.scope["headers"]
            }
        return self._request_headers

    @property
    def duration(self):
        return self.timing.total_duration_seconds()

    def on_asgi_message(self, message):
        if message["type"] == "http.response.start":
            self.status_code = message["status"]
            self.response_headers = {
                k.decode("ascii"): v.decode("ascii") for k, v in message["headers"]
            }
        elif message["type"] == "http.response.body":
            self.response_length += len(message.get("body", ""))

    def _request_header(self, key):
        return self.request_headers.get(key.lower())

    def _response_header(self, key):
        return self.response_headers.get(key.lower())

    def _wsgi_environ_variable(self, key):
        # FIXME: provide fallbacks to access WSGI environ (at least the
        # required variables).
        return None

    def __getitem__(self, key):
        if key in self.HANDLERS:
            retval = self.HANDLERS[key](self)
        elif key.startswith("{"):
            if key.endswith("}i"):
                retval = self._request_header(key[1:-2])
            elif key.endswith("}o"):
                retval = self._response_header(key[1:-2])
            elif key.endswith("}e"):
                retval = self._wsgi_environ_variable(key[1:-2])
            else:
                retval = None
        else:
            retval = None

        if retval is None:
            return "-"
        if isinstance(retval, str):
            return retval.replace('"', '\\"')
        return retval

    HANDLERS = {}

    def _register_handler(key, handlers=HANDLERS):
        def decorator(fn):
            handlers[key] = fn
            return fn

        return decorator

    @_register_handler("h")
    def _remote_address(self, *args, **kwargs):
        return self.scope["client"][0]

    @_register_handler("l")
    def _dash(self, *args, **kwargs):
        return "-"

    @_register_handler("u")
    def _user_name(self, *args, **kwargs):
        pass

    @_register_handler("t")
    def date_of_the_request(self, *args, **kwargs):
        """Date and time in Apache Common Log Format"""
        return time.strftime("[%d/%b/%Y:%H:%M:%S %z]")

    @_register_handler("r")
    def status_line(self, *args, **kwargs):
        full_raw_path = self.scope["raw_path"] + self.scope["query_string"]
        full_path = full_raw_path.decode("ascii")
        return "{method} {full_path} HTTP/{http_version}".format(
            full_path=full_path, **self.scope
        )

    @_register_handler("m")
    def request_method(self, *args, **kwargs):
        return self.scope["method"]

    @_register_handler("U")
    def url_path(self, *args, **kwargs):
        return self.scope["raw_path"].decode("ascii")

    @_register_handler("q")
    def query_string(self, *args, **kwargs):
        return self.scope["query_string"].decode("ascii")

    @_register_handler("H")
    def protocol(self, *args, **kwargs):
        return "HTTP/%s" % self.scope["http_version"]

    @_register_handler("s")
    def status(self, *args, **kwargs):
        return self.status_code or "-"

    @_register_handler("B")
    def response_length(self, *args, **kwargs):
        return self.response_length

    @_register_handler("b")
    def response_length_or_dash(self, *args, **kwargs):
        return self.response_length or "-"

    @_register_handler("f")
    def referer(self, *args, **kwargs):
        val = self.request_headers.get(b"referer")
        if val is None:
            return None
        return val.decode("ascii")

    @_register_handler("a")
    def user_agent(self, *args, **kwargs):
        val = self.request_headers.get(b"user-agent")
        if val is None:
            return None
        return val.decode("ascii")

    @_register_handler("T")
    def request_time_seconds(self, *args, **kwargs):
        return int(self.duration)

    @_register_handler("D")
    def request_time_microseconds(self, *args, **kwargs):
        return int(self.duration * 1_000_000)

    @_register_handler("L")
    def request_time_decimal_seconds(self, *args, **kwargs):
        return "%.6f" % self.duration

    @_register_handler("p")
    def process_id(self, *args, **kwargs):
        return "<%s>" % getpid()

    def __iter__(self):
        # FIXME: add WSGI environ
        yield from self.HANDLERS
        for k, _ in self.scope["headers"]:
            yield "{%s}i" % k.lower()
        for k in self.response_headers:
            yield "{%s}o" % k.lower()

    def __len__(self):
        # FIXME: add WSGI environ
        return (
            len(self.HANDLERS)
            + len(self.scope["headers"] or ())
            + len(self.response_headers)
        )
