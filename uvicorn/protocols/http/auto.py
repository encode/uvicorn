from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from asyncio import Protocol
    from typing import Type

AutoHTTPProtocol: Type[Protocol]
try:
    import httptools  # noqa
except ImportError:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol

    AutoHTTPProtocol = H11Protocol
else:  # pragma: no cover
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

    AutoHTTPProtocol = HttpToolsProtocol
