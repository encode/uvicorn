import sys
from typing import Any, Awaitable, Callable, Dict, Optional, Type, Union

if sys.version_info < (3, 8):
    from typing_extensions import Literal, Protocol, TypedDict
else:
    from typing import Literal, Protocol, TypedDict


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


Scope = Dict[str, Any]
Message = Dict[str, Any]

Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class ASGI2Protocol(Protocol):
    def __init__(self, scope: Scope) -> None:
        ...

    async def __call__(self, receive: Receive, send: Send) -> None:
        ...


ASGI2App = Type[ASGI2Protocol]
ASGI3App = Callable[[Scope, Receive, Send], Awaitable[None]]
ASGIApp = Union[ASGI2App, ASGI3App]
