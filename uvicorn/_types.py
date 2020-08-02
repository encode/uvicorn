import socket
from os import PathLike
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    MutableMapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Type,
    Union,
)

if TYPE_CHECKING:  # pragma: no cover
    from uvloop.loop import TCPTransport

    from uvicorn import Config
    from uvicorn.main import ServerState
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


class ASGI2Protocol(Protocol):
    # Should replace with a Protocol when PEP 544 is accepted.

    def __init__(self, scope: dict) -> None:
        ...

    async def __call__(self, receive: Callable, send: Callable) -> None:
        ...


ASGI2App = Type[ASGI2Protocol]

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ASGI3App = Callable[[Scope, Receive, Send], Awaitable[None]]

ASGIApp = Union[ASGI2App, ASGI3App]

App = Union[ASGIApp, Callable]

Sockets = Optional[List[socket.socket]]

HeaderTypes = Union[
    Dict[str, str],
    Dict[bytes, bytes],
    Sequence[Tuple[str, str]],
    Sequence[Tuple[bytes, bytes]],
]

AutoHTTPProtocolType = Type[Union["H11Protocol", "HttpToolsProtocol"]]

AutoWebSocketsProtocolType = Type[Union["WebSocketProtocol", "WSProtocol"]]


StrPath = Union[str, "PathLike[str]"]

TransportType = Union["TCPTransport"]

