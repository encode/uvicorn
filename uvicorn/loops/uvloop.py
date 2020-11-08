"""
Backwards compatibility shim.
"""
from .._impl.asyncio.loops.uvloop import uvloop_setup

__all__ = ["uvloop_setup"]
