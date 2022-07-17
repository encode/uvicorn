import asyncio
from typing import Optional, Type

AutoWebSocketsProtocol: Optional[Type[asyncio.Protocol]]
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
