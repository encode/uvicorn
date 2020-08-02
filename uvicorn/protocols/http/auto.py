from uvicorn._types import AutoHTTPProtocolType

AutoHTTPProtocol: AutoHTTPProtocolType
try:
    import httptools  # noqa
except ImportError:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol

    AutoHTTPProtocol = H11Protocol
else:
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

    AutoHTTPProtocol = HttpToolsProtocol
