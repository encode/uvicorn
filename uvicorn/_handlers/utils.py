import asyncio
import http
import socket
import urllib.parse
from typing import Optional, Tuple


def _get_status_phrase(status_code: int) -> bytes:
    try:
        return http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        return b""


STATUS_PHRASES = {
    status_code: _get_status_phrase(status_code) for status_code in range(100, 600)
}


def get_sock_remote_addr(sock: socket.SocketType) -> Optional[Tuple[str, int]]:
    try:
        info = sock.getpeername()
    except OSError:
        # This case appears to inconsistently occur with uvloop
        # bound to a unix domain socket.
        return None
    else:
        return (str(info[0]), int(info[1])) if isinstance(info, tuple) else None


def get_sock_local_addr(sock: socket.SocketType) -> Optional[Tuple[str, int]]:
    info = sock.getsockname()
    if isinstance(info, tuple):
        return (str(info[0]), int(info[1]))
    return None


def is_ssl(writer: asyncio.StreamWriter) -> bool:
    transport = writer.transport
    return bool(transport.get_extra_info("sslcontext"))


def get_client_addr(scope: dict) -> str:
    client = scope.get("client")
    if not client:
        return ""
    return "%s:%d" % client


def get_path_with_query_string(scope: dict) -> str:
    path_with_query_string = urllib.parse.quote(
        scope.get("root_path", "") + scope["path"]
    )
    if scope["query_string"]:
        path_with_query_string = "{}?{}".format(
            path_with_query_string, scope["query_string"].decode("ascii")
        )
    return path_with_query_string
