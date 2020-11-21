import http
import socket
from email.utils import formatdate
from typing import List, Optional, Tuple
from urllib.parse import quote


def _get_status_phrase(status_code: int) -> bytes:
    try:
        return http.HTTPStatus(status_code).phrase.encode()
    except ValueError:
        return b""


STATUS_PHRASES = {
    status_code: _get_status_phrase(status_code) for status_code in range(100, 600)
}

RECV_CHUNK_SIZE = 2 ** 16

TRACE_LOG_LEVEL = 5


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


def get_path_with_query_string(scope: dict) -> str:
    path = quote(scope.get("root_path", "") + scope["path"])
    qs = scope["query_string"]
    if qs:
        path += "?{}".format(qs.decode("ascii"))
    return path


def to_internet_date(value: float) -> str:
    return formatdate(value, usegmt=True)


def find_upgrade_header(headers: List[Tuple[bytes, bytes]]) -> Optional[bytes]:
    connection = next((value for name, value in headers if name == b"connection"), None)

    if connection is None:
        return None

    tokens = [token.lower().strip() for token in connection.split(b",")]

    if b"upgrade" not in tokens:
        return None

    return next(value.lower() for name, value in headers if name == b"upgrade")
