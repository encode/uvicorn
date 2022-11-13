import asyncio
from typing import Type

AutoHTTPProtocol: Type[asyncio.Protocol]

try:
    import httparse  # noqa
except ImportError:  # pragma: no cover
    try:
        import httptools  # noqa
    except ImportError:  # pragma: no cover
        from uvicorn.protocols.http.h11_impl import H11Protocol

        AutoHTTPProtocol = H11Protocol
    else:  # pragma: no cover
        from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

        AutoHTTPProtocol = HttpToolsProtocol
else:
    from uvicorn.protocols.http.httparse_impl import HttparseProtocol

    AutoHTTPProtocol = HttparseProtocol
