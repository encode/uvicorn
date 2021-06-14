import asyncio
import time
import urllib.parse
from typing import Optional, Tuple

from asgiref.typing import WWWScope


def get_remote_addr(transport: asyncio.Transport) -> Optional[Tuple[str, int]]:
    socket_info = transport.get_extra_info("socket")
    if socket_info is not None:
        try:
            info = socket_info.getpeername()
            return (str(info[0]), int(info[1])) if isinstance(info, tuple) else None
        except OSError:
            # This case appears to inconsistently occur with uvloop
            # bound to a unix domain socket.
            return None

    info = transport.get_extra_info("peername")
    if info is not None and isinstance(info, (list, tuple)) and len(info) == 2:
        return (str(info[0]), int(info[1]))
    return None


def get_local_addr(transport: asyncio.Transport) -> Optional[Tuple[str, int]]:
    socket_info = transport.get_extra_info("socket")
    if socket_info is not None:
        info = socket_info.getsockname()

        return (str(info[0]), int(info[1])) if isinstance(info, tuple) else None
    info = transport.get_extra_info("sockname")
    if info is not None and isinstance(info, (list, tuple)) and len(info) == 2:
        return (str(info[0]), int(info[1]))
    return None


def is_ssl(transport: asyncio.Transport) -> bool:
    return bool(transport.get_extra_info("sslcontext"))


def get_client_addr(scope: WWWScope) -> str:
    client = scope.get("client")
    if not client:
        return ""
    return "%s:%d" % client


def get_path_with_query_string(scope: WWWScope) -> str:
    path_with_query_string = urllib.parse.quote(
        scope.get("root_path", "") + scope["path"]
    )
    if scope["query_string"]:
        path_with_query_string = "{}?{}".format(
            path_with_query_string, scope["query_string"].decode("ascii")
        )
    return path_with_query_string


class RequestResponseTiming:
    def __init__(self):
        self.request_start_time: Optional[int] = None
        self.request_end_time: Optional[int] = None
        self.response_start_time: Optional[int] = None
        self.response_end_time: Optional[int] = None

    def request_started(self):
        self.request_start_time = time.monotonic()

    def request_ended(self):
        self.request_end_time = time.monotonic()

    def response_started(self):
        self.response_start_time = time.monotonic()

    def response_ended(self):
        self.response_end_time = time.monotonic()

    def request_duration_seconds(self):
        return self.request_end_time - self.request_start_time

    def response_duration_seconds(self):
        return self.response_end_time - self.response_start_time

    def total_duration_seconds(self):
        return self.response_end_time - self.request_start_time
