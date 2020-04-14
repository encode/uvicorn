import socket
import sys


def get_remote_addr(transport):
    socket_info = transport.get_extra_info("socket")
    if socket_info is not None:
        try:
            info = socket_info.getpeername()
        except OSError:
            # This case appears to inconsistently occur with uvloop
            # bound to a unix domain socket.
            family = None
            info = None
        else:
            family = socket_info.family

        if not sys.platform.startswith("win"):
            if family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
                return (str(info[0]), int(info[1]))
        else:
            if family in (socket.AF_INET, socket.AF_INET6):
                return (str(info[0]), int(info[1]))
        return None
    info = transport.get_extra_info("peername")
    if info is not None and isinstance(info, (list, tuple)) and len(info) == 2:
        return (str(info[0]), int(info[1]))
    return None


def get_local_addr(transport):
    socket_info = transport.get_extra_info("socket")
    if socket_info is not None:
        info = socket_info.getsockname()
        family = socket_info.family
        if not sys.platform.startswith("win"):
            if family in (socket.AF_INET, socket.AF_INET6, socket.AF_UNIX):
                return (str(info[0]), int(info[1]))
        else:
            if family in (socket.AF_INET, socket.AF_INET6):
                return (str(info[0]), int(info[1]))
        return None
    info = transport.get_extra_info("sockname")
    if info is not None and isinstance(info, (list, tuple)) and len(info) == 2:
        return (str(info[0]), int(info[1]))
    return None


def is_ssl(transport):
    return bool(transport.get_extra_info("sslcontext"))


def get_client_addr(scope):
    client = scope.get("client")
    if not client:
        return ""
    return "%s:%d" % client


def get_path_with_query_string(scope):
    path_with_query_string = scope.get("root_path", "") + scope["path"]
    if scope["query_string"]:
        path_with_query_string = "{}?{}".format(
            path_with_query_string, scope["query_string"].decode("ascii")
        )
    return path_with_query_string
