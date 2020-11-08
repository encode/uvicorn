"""
Backwards compatibility shim.
"""
from .._impl.asyncio.loops.auto import auto_loop_setup

__all__ = ["auto_loop_setup"]
