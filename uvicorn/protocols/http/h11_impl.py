"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.http.h11_impl import H11Protocol

__all__ = ["H11Protocol"]
