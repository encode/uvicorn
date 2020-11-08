"""
Backwards compatibility shim.
"""
from uvicorn._impl.asyncio.protocols.utils import (
    get_client_addr,
    get_local_addr,
    get_path_with_query_string,
    get_remote_addr,
    is_ssl,
)

__all__ = [
    "get_client_addr",
    "get_local_addr",
    "get_path_with_query_string",
    "get_remote_addr",
    "is_ssl",
]
