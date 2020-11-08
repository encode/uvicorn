"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.http.httptools_impl import HttpToolsProtocol

__all__ = ["HttpToolsProtocol"]
