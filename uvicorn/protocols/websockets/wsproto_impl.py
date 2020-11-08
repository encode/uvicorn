"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.websockets.wsproto_impl import WSProtocol

__all__ = ["WSProtocol"]
