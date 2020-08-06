import urllib
from typing import Optional, Tuple, Union

from uvloop.loop import TCPTransport

from uvicorn._types import Scope, HTTPConnectionScope


def get_remote_addr(transport: TCPTransport) -> Optional[Tuple[str, int]]:
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


def get_local_addr(transport: TCPTransport) -> Optional[Tuple[str, int]]:
    socket_info = transport.get_extra_info("socket")
    if socket_info is not None:
        info = socket_info.getsockname()

        return (str(info[0]), int(info[1])) if isinstance(info, tuple) else None
    info = transport.get_extra_info("sockname")
    if info is not None and isinstance(info, (list, tuple)) and len(info) == 2:
        return (str(info[0]), int(info[1]))
    return None


def is_ssl(transport: TCPTransport) -> bool:
    return bool(transport.get_extra_info("sslcontext"))


def get_client_addr(scope: Union[Scope, HTTPConnectionScope]) -> str:
    client = scope.get("client")
    if not client:
        return ""
    return "%s:%d" % client


def get_path_with_query_string(scope: Union[Scope, HTTPConnectionScope]) -> str:
    path_with_query_string = urllib.parse.quote(
        scope.get("root_path", "") + scope["path"]
    )
    if scope["query_string"]:
        path_with_query_string = "{}?{}".format(
            path_with_query_string, scope["query_string"].decode("ascii")
        )
    return path_with_query_string
