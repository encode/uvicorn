"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.websockets.auto import AutoWebSocketsProtocol

__all__ = ["AutoWebSocketsProtocol"]
