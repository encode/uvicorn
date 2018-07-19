try:
    import httptools
except ImportError:  # pragma: no cover
    from uvicorn.protocols.http.h11 import H11Protocol

    AutoHTTPProtocol = H11Protocol
else:
    from uvicorn.protocols.http.httptools import HttpToolsProtocol

    AutoHTTPProtocol = HttpToolsProtocol
