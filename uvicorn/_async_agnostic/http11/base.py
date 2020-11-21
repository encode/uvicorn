from ..base import BaseHTTPConnection


class BaseHTTP11Connection(BaseHTTPConnection):
    def states(self) -> dict:
        raise NotImplementedError  # pragma: no cover
