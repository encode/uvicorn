import socket
from asyncio import Transport
from os import PathLike
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    List,
    Literal,
    MutableMapping,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    Union,
)

from uvloop.loop import TCPTransport

if TYPE_CHECKING:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

Scope = MutableMapping[str, Any]

ASGIDict = TypedDict(
    "ASGIDict", {"version": str, "spec_version": Union[Literal["2.0"], Literal["2.1"]]}
)

# useless until there is a possibility to add extra keys
# https://github.com/python/mypy/issues/4617

# EnvironType = TypedDict(
#     "EnvironType",
#     {
#         "REQUEST_METHOD": str,
#         "SCRIPT_NAME": str,
#         "PATH_INFO": str,
#         "QUERY_STRING": str,
#         "SERVER_PROTOCOL": str,
#         "wsgi.version": Tuple[int, int],
#         "wsgi.url_scheme": str,
#         "wsgi.input": BytesIO,
#         "wsgi.errors": TextIO,
#         "wsgi.multithread": bool,
#         "wsgi.multiprocess": bool,
#         "wsgi.run_once": bool,
#         "SERVER_NAME": str,
#         "SERVER_PORT": int,
#         "REMOTE_ADDR": str,
#         "CONTENT_LENGTH": str,
#         "CONTENT_TYPE": str,
#     },
# )

HTTPConnectionScope = TypedDict(
    "HTTPConnectionScope",
    {
        "type": Literal["http"],
        "asgi": ASGIDict,
        "http_version": Union[Literal["1.0"], Literal["1.1"], Literal["2"]],
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


class HTTPConnectionScopeExtended(HTTPConnectionScope):
    body: str
    bytes: str
    text: str


# Message = MutableMapping[str, Any]

HTTPReceiveRequest = TypedDict(
    "HTTPReceiveRequest",
    {"type": Literal["http.request"], "body": bytes, "more_body": bool},
)
HTTPReceiveDisconnect = TypedDict(
    "HTTPReceiveDisconnect", {"type": Literal["http.disconnect"]}
)
HTTPReceiveMessage = Union[HTTPReceiveRequest, HTTPReceiveDisconnect]
WSReceiveConnect = TypedDict("WSReceiveConnect", {"type": "websocket.connect"})
WSReceive = TypedDict(
    "WSReceive", {"type": Literal["websocket.receive"], "bytes": bytes, "text": str}
)
WSReceiveDisconnect = TypedDict(
    "WSReceiveDisconnect", {"type": Literal["websocket.disconnect"], "code": int}
)
WSReceiveMessage = Union[WSReceiveConnect, WSReceive, WSReceiveDisconnect]

HTTPSendResponseStart = TypedDict(
    "HTTPSendResponseStart",
    {
        "type": Literal["http.response.start"],
        "status": int,
        "headers": Sequence[Tuple[bytes, bytes]],
    },
)
HTTPSendResponseBody = TypedDict(
    "HTTPSendResponseBody",
    {"type": Literal["http.response.body"], "body": bytes, "more_body": Optional[bool]},
)

HTTPSendMessage = Union[HTTPSendResponseBody, HTTPSendResponseStart]


WSSendAccept = TypedDict(
    "WSSendAccept",
    {
        "type": Literal["websocket.accept"],
        "subprotocol": str,
        "headers": Sequence[Tuple[bytes, bytes]],
    },
)

WSSend = TypedDict("WSSend", {"type": Literal["websocket.disconnect"], "code": int})
WSSendClose = TypedDict(
    "WSSendClose", {"type": Literal["websocket.close"], "code": int}
)
WSSendMessage = Union[WSSendAccept, WSSend, WSSendClose]

Receive = Callable[[], Awaitable[HTTPReceiveMessage]]
Send = Callable[[HTTPSendMessage], Awaitable[None]]

ASGI3App = Callable[[HTTPConnectionScope, Receive, Send], Awaitable[None]]

Sockets = Optional[List[socket.socket]]

HeaderTypes = Union[
    Sequence[Tuple[bytes, bytes]], Sequence[Tuple[str, str]],
]

AutoHTTPProtocolType = Type[Union["H11Protocol", "HttpToolsProtocol"]]

AutoWebSocketsProtocolType = Type[Union["WebSocketProtocol", "WSProtocol"]]

StrPath = Union[str, PathLike]

TransportType = Union[TCPTransport, Transport]
