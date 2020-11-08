"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.http.auto import AutoHTTPProtocol

__all__ = ["AutoHTTPProtocol"]
