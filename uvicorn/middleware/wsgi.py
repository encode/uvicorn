try:
    from a2wsgi import WSGIMiddleware
except ImportError:
    from typing import Any

    class WSGIMiddleware:  # type: ignore
        def __init__(self, *_: Any) -> None:
            raise RuntimeError(
                "Make sure you have 'a2wsgi' installed to handle WSGI apps"
            )


__all__ = ["WSGIMiddleware"]
