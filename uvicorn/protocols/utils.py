from __future__ import annotations

import asyncio
import ssl
import urllib.parse
import sys

from uvicorn._types import WWWScope
from uvicorn.config import Config


class ClientDisconnected(OSError): ...


def get_remote_addr(transport: asyncio.Transport) -> tuple[str, int] | None:
    socket_info = transport.get_extra_info("socket")
    if socket_info is not None:
        try:
            info = socket_info.getpeername()
            return (str(info[0]), int(info[1])) if isinstance(info, tuple) else None
        except OSError:  # pragma: no cover
            # This case appears to inconsistently occur with uvloop
            # bound to a unix domain socket.
            return None

    info = transport.get_extra_info("peername")
    if info is not None and isinstance(info, (list, tuple)) and len(info) == 2:
        return (str(info[0]), int(info[1]))
    return None


def get_local_addr(transport: asyncio.Transport) -> tuple[str, int] | None:
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
    path_with_query_string = urllib.parse.quote(scope["path"])
    if scope["query_string"]:
        path_with_query_string = "{}?{}".format(path_with_query_string, scope["query_string"].decode("ascii"))
    return path_with_query_string



def get_tls_info(transport: asyncio.Transport, server_config: Config) -> dict[object, object]:
    ###
    # server_cert: Unable to set from transport information, need to set from server_config
    # client_cert_chain: 
    # tls_version:
    # cipher_suite:
    ###

    ssl_info: dict[object, object] = {
        "server_cert": None,
        "client_cert_chain": [],
        "tls_version": None,
        "cipher_suite": None,
    }

    ssl_info["server_cert"] = server_config.ssl_cert_pem

    ssl_object = transport.get_extra_info("ssl_object")
    if not ssl_object:
        return ssl_info
    
    if sys.version_info < (3, 13):
        peer_cert = ssl_object.getpeercert(binary_form=True)
        if peer_cert:
            ssl_info["client_cert_chain"].append(ssl.DER_cert_to_PEM_cert(peer_cert))
    else:
        client_chain = ssl_object.get_verified_chain()
        for cert in client_chain:
            ssl_info["client_cert_chain"].append(ssl.DER_cert_to_PEM_cert(cert))
        
    ssl_info["tls_version"] = ssl_object.version()
    ssl_info["cipher_suite"] = ssl_object.cipher()[0] if ssl_object.cipher() else None

    return ssl_info
