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
    TypedDict,
    Union,
)

# from typing_extensions import TypedDict
from uvloop.loop import TCPTransport

if TYPE_CHECKING:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


Scope = MutableMapping[str, Any]

ASGIDict = TypedDict("ASGIDict", {"version": str, "spec_version": Union["2.0", "2.1"]})
HTTPConnectionScope = TypedDict(
    "HTTPConnectionScope",
    {
        "type": "http",
        "asgi": ASGIDict,
        "http_version": Union["1.0", "1.1", "2"],
        "method": str,
        "scheme": str,
        "path": str,
        "raw_path": bytes,
        "query_string": bytes,
        "root_path": str,
        "headers": Sequence[Tuple[bytes, bytes]],
        "client": Optional[Tuple[str, int]],
        "server": Optional[Tuple[str, int]],
    },
)
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ASGI3App = Callable[[Union[Scope, HTTPConnectionScope], Receive, Send], Awaitable[None]]

Sockets = Optional[List[socket.socket]]

HeaderTypes = Union[
    Sequence[Tuple[bytes, bytes]], Sequence[Tuple[str, str]],
]

AutoHTTPProtocolType = Type[Union["H11Protocol", "HttpToolsProtocol"]]

AutoWebSocketsProtocolType = Type[Union["WebSocketProtocol", "WSProtocol"]]


StrPath = Union[str, PathLike]

TransportType = Union[TCPTransport, Transport]
