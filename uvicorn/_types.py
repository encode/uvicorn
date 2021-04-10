import sys
from typing import Awaitable, Callable, Dict, Iterable, Optional, Tuple, Type, Union

if sys.version_info < (3, 8):
    from typing_extensions import Literal, Protocol, TypedDict
else:
    from typing import Literal, TypedDict


class ASGISpecInfo(TypedDict):
    version: str
    spec_version: Optional[Literal["2.0", "2.1"]]


class LifespanScope(TypedDict):
    type: Literal["lifespan"]
    asgi: ASGISpecInfo


class LifespanReceiveMessage(TypedDict):
    type: Literal["lifespan.startup", "lifespan.shutdown"]


class LifespanSendMessage(TypedDict):
    type: Literal[
        "lifespan.startup.complete",
        "lifespan.startup.failed",
        "lifespan.shutdown.complete",
        "lifespan.shutdown.failed",
    ]
    message: Optional[str]


class HTTPScope(TypedDict):
    type: Literal["http"]
    asgi: ASGISpecInfo
    http_version: str
    method: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: Iterable[Tuple[bytes, bytes]]
    client: Optional[Tuple[str, int]]
    server: Optional[Tuple[str, Optional[int]]]
    extensions: Dict[str, Dict[object, object]]


class WebsocketScope(TypedDict):
    type: Literal["websocket"]
    asgi: ASGISpecInfo
    http_version: str
    scheme: str
    path: str
    raw_path: bytes
    query_string: bytes
    root_path: str
    headers: Iterable[Tuple[bytes, bytes]]
    client: Optional[Tuple[str, int]]
    server: Optional[Tuple[str, Optional[int]]]
    subprotocols: Iterable[str]
    extensions: Dict[str, Dict[object, object]]


WWWScope = Union[HTTPScope, WebsocketScope]
Scope = Union[HTTPScope, WebsocketScope, LifespanScope]


class HTTPRequestEvent(TypedDict):
    type: Literal["http.request"]
    body: bytes
    more_body: bool


class HTTPResponseStartEvent(TypedDict):
    type: Literal["http.response.start"]
    status: int
    headers: Iterable[Tuple[bytes, bytes]]


class HTTPResponseBodyEvent(TypedDict):
    type: Literal["http.response.body"]
    body: bytes
    more_body: bool


class HTTPServerPushEvent(TypedDict):
    type: Literal["http.response.push"]
    path: str
    headers: Iterable[Tuple[bytes, bytes]]


class HTTPDisconnectEvent(TypedDict):
    type: Literal["http.disconnect"]


class WebsocketConnectEvent(TypedDict):
    type: Literal["websocket.connect"]


class WebsocketAcceptEvent(TypedDict):
    type: Literal["websocket.accept"]
    subprotocol: Optional[str]
    headers: Iterable[Tuple[bytes, bytes]]


class WebsocketReceiveEvent(TypedDict):
    type: Literal["websocket.receive"]
    bytes: Optional[bytes]
    text: Optional[str]


class WebsocketSendEvent(TypedDict):
    type: Literal["websocket.send"]
    bytes: Optional[bytes]
    text: Optional[str]


class WebsocketResponseStartEvent(TypedDict):
    type: Literal["websocket.http.response.start"]
    status: int
    headers: Iterable[Tuple[bytes, bytes]]


class WebsocketResponseBodyEvent(TypedDict):
    type: Literal["websocket.http.response.body"]
    body: bytes
    more_body: bool


class WebsocketDisconnectEvent(TypedDict):
    type: Literal["websocket.disconnect"]
    code: int


class WebsocketCloseEvent(TypedDict):
    type: Literal["websocket.close"]
    code: int
    reason: Optional[str]


class LifespanStartupEvent(TypedDict):
    type: Literal["lifespan.startup"]


class LifespanShutdownEvent(TypedDict):
    type: Literal["lifespan.shutdown"]


class LifespanStartupCompleteEvent(TypedDict):
    type: Literal["lifespan.startup.complete"]


class LifespanStartupFailedEvent(TypedDict):
    type: Literal["lifespan.startup.failed"]
    message: str


class LifespanShutdownCompleteEvent(TypedDict):
    type: Literal["lifespan.shutdown.complete"]


class LifespanShutdownFailedEvent(TypedDict):
    type: Literal["lifespan.shutdown.failed"]
    message: str


ASGIReceiveEvent = Union[
    HTTPRequestEvent,
    HTTPDisconnectEvent,
    WebsocketConnectEvent,
    WebsocketReceiveEvent,
    WebsocketDisconnectEvent,
    LifespanStartupEvent,
    LifespanShutdownEvent,
]


ASGISendEvent = Union[
    HTTPResponseStartEvent,
    HTTPResponseBodyEvent,
    HTTPServerPushEvent,
    HTTPDisconnectEvent,
    WebsocketAcceptEvent,
    WebsocketSendEvent,
    WebsocketResponseStartEvent,
    WebsocketResponseBodyEvent,
    WebsocketCloseEvent,
    LifespanStartupCompleteEvent,
    LifespanStartupFailedEvent,
    LifespanShutdownCompleteEvent,
    LifespanShutdownFailedEvent,
]


ASGIReceiveCallable = Callable[[], Awaitable[ASGIReceiveEvent]]
ASGISendCallable = Callable[[ASGISendEvent], Awaitable[None]]


class ASGI2Protocol(Protocol):
    def __init__(self, scope: Scope) -> None:
        ...

    async def __call__(
        self, receive: ASGIReceiveCallable, send: ASGISendCallable
    ) -> None:
        ...


ASGI2Application = Type[ASGI2Protocol]
ASGI3Application = Callable[
    [Scope, ASGIReceiveCallable, ASGISendCallable],
    Awaitable[None],
]
ASGIApplication = Union[ASGI2Application, ASGI3Application]
