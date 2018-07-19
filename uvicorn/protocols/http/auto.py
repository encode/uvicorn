def AutoHTTPProtocol(*args, **kwargs):
    try:
        import httptools
    except ImportError:  # pragma: no cover
        from uvicorn.protocols.http.h11 import H11Protocol

        return H11Protocol(*args, **kwargs)
    else:
        from uvicorn.protocols.http.httptools import HttpToolsProtocol

        return HttpToolsProtocol(*args, **kwargs)
