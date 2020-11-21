import itertools
import logging
from typing import Any

TRACE_LOG_LEVEL = 5
NEXT_ID = itertools.count()


class ConnectionLogger(logging.Logger):
    def __init__(self) -> None:
        # Unique ID to include in debug output.
        self._obj_id = next(NEXT_ID)
        self._logger = logging.getLogger("uvicorn.error")

    def trace(self, msg: str, *args: Any) -> None:
        self._logger.log(TRACE_LOG_LEVEL, f"%s: {msg}", *args)
