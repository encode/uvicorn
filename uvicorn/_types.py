import sys
from typing import Optional, Union

if sys.version_info < (3, 8):
    from typing_extensions import Literal, TypedDict
else:
    from typing import Literal, TypedDict

# SCOPES


class ASGIDict(TypedDict):
    version: str
    spec_version: Optional[Union[Literal["2.0"], Literal["2.1"]]]


class LifespanScope(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#scope
    """

    type: Literal["lifespan"]
    asgi: ASGIDict


# lifespan messages receive
class LifespanReceiveStartup(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-receive-event
    """

    type: Literal["lifespan.startup"]


class LifeSpanReceiveShutdown(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-receive-event
    """

    type: Literal["lifespan.shutdown"]


LifespanReceiveMessage = Union[LifespanReceiveStartup, LifeSpanReceiveShutdown]

# lifespan messages send


class LifespanSendStartupComplete(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-complete-send-event
    """

    type: Literal["lifespan.startup.complete"]


class LifespanSendStartupFailed(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#startup-failed-send-event
    """

    type: Literal["lifespan.startup.failed"]
    message: Optional[str]


class LifespanSendShutdownComplete(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-complete-send-event
    """

    type: Literal["lifespan.shutdown.complete"]


class LifespanSendShutdownFailed(TypedDict):
    """
    https://asgi.readthedocs.io/en/latest/specs/lifespan.html#shutdown-failed-send-event
    """

    type: Literal["lifespan.shutdown.failed"]
    message: Optional[str]


LifespanSendMessage = Union[
    LifespanSendStartupComplete,
    LifespanSendStartupFailed,
    LifespanSendShutdownComplete,
    LifespanSendShutdownFailed,
]
