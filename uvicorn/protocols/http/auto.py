import asyncio
from typing import Type

AutoHTTPProtocol: Type[asyncio.Protocol]
try:
    import httptools  # noqa

    assert (
        httptools.__version__ >= "0.2.0"
    ), "Uvicorn requires httptools version 0.2.0 or higher"
except ImportError:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol

    AutoHTTPProtocol = H11Protocol
else:  # pragma: no cover
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

    AutoHTTPProtocol = HttpToolsProtocol
