import socket
from asyncio import Transport
from os import PathLike
from typing import (
    TYPE_CHECKING,
    Awaitable,
    Callable,
    List,
    Literal,
    Optional,
    Sequence,
    Tuple,
    Type,
    TypedDict,
    Union,
)

from uvloop.loop import TCPTransport
from websockets import Subprotocol

if TYPE_CHECKING:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol
    from uvicorn.protocols.websockets.wsproto_impl import WSProtocol


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


# SCOPES
ASGIDict = TypedDict(
    "ASGIDict", {"version": str, "spec_version": Union[Literal["2.0"], Literal["2.1"]]}
)

BaseConnectionScope = TypedDict(
    "BaseConnectionScope",
    {
        "asgi": ASGIDict,
        "http_version": Union[Literal["1.0"], Literal["1.1"], Literal["2"]],
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


class HTTPConnectionScope(BaseConnectionScope):
    type: Literal["http"]
    method: str


class WSConnectionScope(BaseConnectionScope):
    type: Literal["websocket"]
    subprotocols: List[str]


Scope = Union[HTTPConnectionScope, WSConnectionScope]

# HTTP messages

## receive
HTTPReceiveRequest = TypedDict(
    "HTTPReceiveRequest",
    {"type": Literal["http.request"], "body": bytes, "more_body": bool},
)
HTTPReceiveDisconnect = TypedDict(
    "HTTPReceiveDisconnect", {"type": Literal["http.disconnect"]}
)
HTTPReceiveMessage = Union[HTTPReceiveRequest, HTTPReceiveDisconnect]

## send
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
    {"type": Literal["http.response.body"], "body": bytes, "more_body": bool},
)

HTTPSendMessage = Union[HTTPSendResponseBody, HTTPSendResponseStart]


# WS messages

## receive
WSReceiveConnect = TypedDict("WSReceiveConnect", {"type": Literal["websocket.connect"]})
WSReceive = TypedDict(
    "WSReceive", {"type": Literal["websocket.receive"], "bytes": bytes, "text": str}
)
WSReceiveDisconnect = TypedDict(
    "WSReceiveDisconnect", {"type": Literal["websocket.disconnect"], "code": int}
)
WSReceiveMessage = Union[WSReceiveConnect, WSReceive, WSReceiveDisconnect]

## send
WSSendAccept = TypedDict(
    "WSSendAccept",
    {
        "type": Literal["websocket.accept"],
        "subprotocol": Optional[Union[str, Subprotocol]],
        "headers": Sequence[Tuple[bytes, bytes]],
    },
)

WSSend = TypedDict("WSSend", {"type": Literal["websocket.disconnect"], "code": int})
WSSendClose = TypedDict(
    "WSSendClose", {"type": Literal["websocket.close"], "code": int}
)
WSSendMessage = Union[WSSendAccept, WSSend, WSSendClose]

## ALL messages
ReceiveMessage = Union[HTTPReceiveMessage, WSReceiveMessage]
SendMessage = Union[HTTPSendMessage, WSSendMessage]

## ALL functions
Receive = Callable[[], Awaitable[ReceiveMessage]]
Send = Callable[[SendMessage], Awaitable[None]]

ASGI3App = Callable[[Scope, Receive, Send], Awaitable[None]]

Sockets = Optional[List[socket.socket]]

HeaderTypes = Union[
    Sequence[Tuple[bytes, bytes]], Sequence[Tuple[str, str]],
]

AutoHTTPProtocolType = Type[Union["H11Protocol", "HttpToolsProtocol"]]

AutoWebSocketsProtocolType = Type[Union["WebSocketProtocol", "WSProtocol"]]

StrPath = Union[str, PathLike]

TransportType = Union[TCPTransport, Transport]
