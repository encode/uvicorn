try:
    import httptools
except ImportError as exc:  # pragma: no cover
    from uvicorn.protocols.http.h11_impl import H11Protocol

    AutoHTTPProtocol = H11Protocol
else:
    from uvicorn.protocols.http.httptools_impl import HttpToolsProtocol

    AutoHTTPProtocol = HttpToolsProtocol
