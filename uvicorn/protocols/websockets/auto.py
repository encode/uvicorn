from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncio import Protocol
    from typing import Optional

AutoWebSocketsProtocol: Optional[type[Protocol]]
try:
    import websockets  # noqa
except ImportError:  # pragma: no cover
    try:
        import wsproto  # noqa
    except ImportError:
        AutoWebSocketsProtocol = None
    else:
        from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

        AutoWebSocketsProtocol = WSProtocol
else:
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol

    AutoWebSocketsProtocol = WebSocketProtocol
