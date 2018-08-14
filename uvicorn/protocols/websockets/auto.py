try:
    import websockets
except ImportError:  # pragma: no cover
    try:
        import wsproto
    except ImportError:
        AutoWebSocketsProtocol = None
    else:
        from uvicorn.protocols.websockets.wsproto_impl import WSProtocol

        AutoWebSocketsProtocol = WSProtocol
else:
    from uvicorn.protocols.websockets.websockets_impl import WebSocketProtocol

    AutoWebSocketsProtocol = WebSocketProtocol
