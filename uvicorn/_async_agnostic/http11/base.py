from ..base import BaseHTTPConnection


class BaseHttp11Connection(BaseHTTPConnection):
    def states(self) -> dict:
        raise NotImplementedError  # pragma: no cover
