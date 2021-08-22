"""
This module backports `asyncio.run` to Python 3.6.
You can check the original implementation on:
https://github.com/python/cpython/blob/3.7/Lib/asyncio/runners.py
"""
import sys

__all__ = ("run", "get_running_loop")

if sys.version_info >= (3, 7):
    from asyncio import get_running_loop, run
else:
    from asyncio_backport import get_running_loop, run
