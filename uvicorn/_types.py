import types
import typing

from typing_extensions import NotRequired

# WSGI
Environ = typing.MutableMapping[str, typing.Any]
ExcInfo = typing.Tuple[
    typing.Type[BaseException], BaseException, typing.Optional[types.TracebackType]
]
StartResponse = typing.Callable[
    [str, typing.Iterable[typing.Tuple[str, str]], typing.Optional[ExcInfo]], None
]
WSGIApp = typing.Callable[
    [Environ, StartResponse], typing.Union[typing.Iterable[bytes], BaseException]
]

# ASGI


class ASGIVersions(typing.TypedDict):
    spec_version: str
    version: typing.Literal["2.0", "3.0"]


class HTTPScope(typing.TypedDict):
    type: typing.Literal["http"]
    asgi: ASGIVersions
    http_version: str
    method: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: typing.Iterable[typing.Tuple[bytes, bytes]]
    client: typing.Optional[typing.Tuple[str, int]]
    server: typing.Optional[typing.Tuple[str, typing.Optional[int]]]
    extensions: NotRequired[typing.Dict[str, typing.Dict[object, object]]]


class WebSocketScope(typing.TypedDict):
    type: typing.Literal["websocket"]
    asgi: ASGIVersions
    http_version: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: typing.Iterable[typing.Tuple[bytes, bytes]]
    client: typing.Optional[typing.Tuple[str, int]]
    server: typing.Optional[typing.Tuple[str, typing.Optional[int]]]
    subprotocols: typing.Iterable[str]
    extensions: NotRequired[typing.Dict[str, typing.Dict[object, object]]]


class LifespanScope(typing.TypedDict):
    type: typing.Literal["lifespan"]
    asgi: ASGIVersions


WWWScope = typing.Union[HTTPScope, WebSocketScope]
Scope = typing.Union[HTTPScope, WebSocketScope, LifespanScope]


class HTTPRequestEvent(typing.TypedDict):
    type: typing.Literal["http.request"]
    body: bytes
    more_body: NotRequired[bool]  # TODO: Confirm this NotRequired.


class HTTPResponseStartEvent(typing.TypedDict):
    type: typing.Literal["http.response.start"]
    status: int
    headers: typing.Iterable[typing.Tuple[bytes, bytes]]  # TODO: Is this NotRequired?


class HTTPResponseBodyEvent(typing.TypedDict):
    type: typing.Literal["http.response.body"]
    body: bytes
    more_body: NotRequired[bool]  # TODO: Confirm this NotRequired.


class HTTPDisconnectEvent(typing.TypedDict):
    type: typing.Literal["http.disconnect"]


class HTTPServerPushEvent(typing.TypedDict):
    type: typing.Literal["http.response.push"]
    path: str
    headers: typing.Iterable[typing.Tuple[bytes, bytes]]  # TODO: Is this NotRequired?


class WebSocketConnectEvent(typing.TypedDict):
    type: typing.Literal["websocket.connect"]


class WebSocketAcceptEvent(typing.TypedDict):
    type: typing.Literal["websocket.accept"]
    subprotocol: typing.Optional[str]  # TODO: Is it NotRequired?
    headers: typing.Iterable[typing.Tuple[bytes, bytes]]  # TODO: Is it NotRequired?


class _WSReceiveEventBytes(typing.TypedDict):
    type: typing.Literal["websocket.receive"]
    bytes: bytes


class _WSReceiveEventText(typing.TypedDict):
    type: typing.Literal["websocket.receive"]
    text: str


WebSocketReceiveEvent = typing.Union[_WSReceiveEventBytes, _WSReceiveEventText]


class _WSSendEventBytes(typing.TypedDict):
    type: typing.Literal["websocket.send"]
    bytes: bytes


class _WSSendEventText(typing.TypedDict):
    type: typing.Literal["websocket.send"]
    text: str


WebSocketSendEvent = typing.Union[_WSSendEventBytes, _WSSendEventText]


class WebSocketResponseStartEvent(typing.TypedDict):
    type: typing.Literal["websocket.http.response.start"]
    status: int
    headers: typing.Iterable[typing.Tuple[bytes, bytes]]  # TODO: Is it NotRequired?


class WebSocketResponseBodyEvent(typing.TypedDict):
    type: typing.Literal["websocket.http.response.body"]
    body: bytes
    more_body: NotRequired[bool]  # TODO: Confirm the NotRequired.


class WebSocketDisconnectEvent(typing.TypedDict):
    type: typing.Literal["websocket.disconnect"]
    code: int  # TODO: Is the code NotRequired?


class WebSocketCloseEvent(typing.TypedDict):
    type: typing.Literal["websocket.close"]
    code: int
    reason: NotRequired[str]  # TODO: Confirm that it is NotRequired.


WebSocketEvent = typing.Union[
    "WebSocketReceiveEvent",
    "WebSocketDisconnectEvent",
    "WebSocketConnectEvent",
]


class LifespanStartupEvent(typing.TypedDict):
    type: typing.Literal["lifespan.startup"]


class LifespanShutdownEvent(typing.TypedDict):
    type: typing.Literal["lifespan.shutdown"]


class LifespanStartupCompleteEvent(typing.TypedDict):
    type: typing.Literal["lifespan.startup.complete"]


class LifespanStartupFailedEvent(typing.TypedDict):
    type: typing.Literal["lifespan.startup.failed"]
    message: str


class LifespanShutdownCompleteEvent(typing.TypedDict):
    type: typing.Literal["lifespan.shutdown.complete"]


class LifespanShutdownFailedEvent(typing.TypedDict):
    type: typing.Literal["lifespan.shutdown.failed"]
    message: str


LifespanReceiveMessage = typing.Union[LifespanStartupEvent, LifespanShutdownEvent]
LifespanSendMessage = typing.Union[
    LifespanStartupFailedEvent,
    LifespanShutdownFailedEvent,
    LifespanStartupCompleteEvent,
    LifespanShutdownCompleteEvent,
]

ASGIReceiveEvent = typing.Union[
    HTTPRequestEvent,
    HTTPDisconnectEvent,
    WebSocketConnectEvent,
    WebSocketReceiveEvent,
    WebSocketDisconnectEvent,
    LifespanStartupEvent,
    LifespanShutdownEvent,
]


ASGISendEvent = typing.Union[
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
    HTTPServerPushEvent,
    HTTPDisconnectEvent,
    WebSocketAcceptEvent,
    WebSocketSendEvent,
    WebSocketResponseStartEvent,
    WebSocketResponseBodyEvent,
    WebSocketCloseEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownCompleteEvent,
    LifespanShutdownFailedEvent,
]


ASGIReceiveCallable = typing.Callable[[], typing.Awaitable[ASGIReceiveEvent]]
ASGISendCallable = typing.Callable[[ASGISendEvent], typing.Awaitable[None]]


class ASGI2Protocol(typing.Protocol):
    def __init__(self, scope: Scope) -> None:
        ...

    async def __call__(
        self, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        ...


ASGI2Application = typing.Type[ASGI2Protocol]
ASGI3Application = typing.Callable[
    [
        Scope,
        ASGIReceiveCallable,
        ASGISendCallable,
    ],
    typing.Awaitable[None],
]
ASGIApplication = typing.Union[ASGI2Application, ASGI3Application]
