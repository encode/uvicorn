from os import PathLike
import socket
from typing import (
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    Union,
)

from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


class ASGI2Protocol(Protocol):
    def __init__(self, scope: dict) -> None:
        ...

    async def __call__(self, receive: Callable, send: Callable) -> None:
        ...


ASGIApp_v2 = Type[ASGI2Protocol]
ASGIApp_v3 = Callable[[dict, Callable, Callable], Awaitable[None]]
ASGIApp = Union[ASGIApp_v3, ASGIApp_v2]

Sockets = Optional[List[socket.socket]]

HeaderTypes = Union[
    Dict[str, str],
    Dict[bytes, bytes],
    Sequence[Tuple[str, str]],
    Sequence[Tuple[bytes, bytes]],
]

AutoHTTPProtocolType = Type[Union[H11Protocol, HttpToolsProtocol]]

AutoWebSocketsProtocolType = Type[Union[WebSocketProtocol, WSProtocol]]


StrPath = Union[str, "PathLike[str]"]
