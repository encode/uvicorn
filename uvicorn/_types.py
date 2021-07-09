import asyncio
import types
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterable,
    MutableMapping,
    Optional,
    Protocol,
    Tuple,
    Type,
    Union,
)

if TYPE_CHECKING:
    from uvicorn.config import Config
    from uvicorn.server_state import ServerState

# WSGI
Environ = MutableMapping[str, Any]
ExcInfo = Tuple[Type[BaseException], BaseException, Optional[types.TracebackType]]
StartResponse = Callable[[str, Iterable[Tuple[str, str]], Optional[ExcInfo]], None]
WSGIApp = Callable[[Environ, StartResponse], Union[Iterable[bytes], BaseException]]


class WebProtocol(Protocol):
    def __init__(
        self,
        config: "Config",
        server_state: "ServerState",
        on_connection_lost: Optional[Callable[..., Any]],
        _loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        ...

    def connection_made(self, transport) -> None:
        ...

    def data_received(self, data: bytes) -> None:
        ...

    def shutdown(self) -> None:
        ...
