import socket
from asyncio import Transport
from os import PathLike
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    List,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    Union,
)

from uvloop.loop import TCPTransport

if TYPE_CHECKING:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ASGI3App = Callable[[Scope, Receive, Send], Awaitable[None]]

Sockets = Optional[List[socket.socket]]

HeaderTypes = Union[
    Sequence[Tuple[bytes, bytes]], Sequence[Tuple[str, str]],
]

AutoHTTPProtocolType = Type[Union["H11Protocol", "HttpToolsProtocol"]]

AutoWebSocketsProtocolType = Type[Union["WebSocketProtocol", "WSProtocol"]]


StrPath = Union[str, PathLike]

TransportType = Union[TCPTransport, Transport]
