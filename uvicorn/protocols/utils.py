import socket


def get_socket_addr(transport, remote):
    socket_info = transport.get_extra_info("socket")
    if remote:
        info = socket_info.getpeername()
    else:
        info = socket_info.getsockname()
    family = socket_info.family
    if family in (socket.AF_INET, socket.AF_INET6):
        return (str(info[0]), int(info[1]))
    return None


def get_remote_addr(transport):
    return get_socket_addr(transport, True)


def get_local_addr(transport):
    return get_socket_addr(transport, False)


def is_ssl(transport):
    return bool(transport.get_extra_info("sslcontext"))
