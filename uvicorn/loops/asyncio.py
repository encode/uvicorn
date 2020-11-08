"""
Backwards compatibility shim.
"""
from .._impl.asyncio.loops.asyncio import asyncio_setup

__all__ = ["asyncio_setup"]
