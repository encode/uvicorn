import logging

try:
    import websockets  # noqa
except ImportError:  # pragma: no cover
    try:
        import wsproto  # noqa
    except ImportError:
        AutoWebSocketsProtocol = None
        logger = logging.getLogger("uvicorn.error")
        logger.warning(
            "No websockets library is installed. You can run pip install "
            "uvicorn[standard] to enable the websockets library or install wsproto "
            "manually"
        )
    else:
        from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

        AutoWebSocketsProtocol = WSProtocol
else:
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol

    AutoWebSocketsProtocol = WebSocketProtocol
