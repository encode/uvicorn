import asyncio
import importlib
import typing

AutoWebSocketsProtocol: typing.Optional[typing.Callable[..., asyncio.Protocol]]
try:
    importlib.import_module("websockets")
except ImportError:  # pragma: no cover
    try:
        importlib.import_module("wsproto")
    except ImportError:
        AutoWebSocketsProtocol = None
    else:
        from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

        AutoWebSocketsProtocol = WSProtocol
else:
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol

    AutoWebSocketsProtocol = WebSocketProtocol
