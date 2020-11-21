import itertools
import logging
import time
from typing import Any, AsyncIterator, List, Optional, Tuple

from .utils import to_internet_date

TRACE_LOG_LEVEL = 5
NEXT_ID = itertools.count()


class BaseHTTPConnection:
    MAX_RECV = 2 ** 16

    def __init__(self) -> None:
        self._obj_id = next(NEXT_ID)
        self._logger = logging.getLogger("uvicorn.error")

    def trace(self, msg: str, *args: Any) -> None:
        self._logger.log(TRACE_LOG_LEVEL, f"conn(%s): {msg}", self._obj_id, *args)

    def debug(self, msg: str, *args: Any) -> None:
        self._logger.debug(f"conn(%s): {msg}", self._obj_id, *args)

    def basic_headers(self) -> List[Tuple[bytes, bytes]]:
        return [
            (b"Date", to_internet_date(time.time()).encode()),
        ]

    @property
    def server(self) -> Optional[Tuple[str, int]]:
        raise NotImplementedError  # pragma: no cover

    @property
    def client(self) -> Optional[Tuple[str, int]]:
        raise NotImplementedError  # pragma: no cover

    @property
    def scheme(self) -> str:
        raise NotImplementedError  # pragma: no cover

    async def read_request(
        self,
    ) -> Tuple[bytes, bytes, bytes, List[Tuple[bytes, bytes]], Optional[bytes]]:
        raise NotImplementedError  # pragma: no cover

    async def aiter_request_body(self) -> AsyncIterator[bytes]:
        raise NotImplementedError  # pragma: no cover

    async def send_response(
        self, status_code: int, headers: List[Tuple[bytes, bytes]], reason: bytes = b""
    ) -> None:
        raise NotImplementedError  # pragma: no cover

    async def send_response_body(self, chunk: bytes) -> None:
        raise NotImplementedError  # pragma: no cover

    async def send_simple_response(
        self, status_code: int, content_type: str, body: bytes
    ) -> None:
        raise NotImplementedError  # pragma: no cover

    def set_keepalive(self) -> None:
        raise NotImplementedError  # pragma: no cover

    async def trigger_shutdown(self) -> None:
        raise NotImplementedError  # pragma: no cover

    async def shutdown_and_clean_up(self) -> None:
        raise NotImplementedError  # pragma: no cover
