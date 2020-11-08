"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.websockets.websockets_impl import WebSocketProtocol

__all__ = ["WebSocketProtocol"]
